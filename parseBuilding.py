#! /usr/bin/python3

import re;
import json;
import xml.etree.ElementTree as ET
import pyproj;

#proj = pyproj.Proj("+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs");
proj = pyproj.Proj(init="epsg:25833");

def getGeometry(bldg):
    global proj;
    textures = {};
    
    for i in bldg.iter("appearance"):
        appr = i.find("Appearance");
        theme = appr.find("theme").text;
        #if (theme != "rgbTexture"):
        #    continue;
        
        for sdm in appr.iter("surfaceDataMember"):
            tex = sdm.find("ParameterizedTexture");
            if not tex:
    #            exit(0);
                continue;
            texId = tex.attrib["id"];
            uri = tex.find("imageURI").text
            target = tex.find("target")
            targetUri = target.attrib["uri"]
            assert(targetUri[0] == "#")
            targetUri = targetUri[1:]
            
            tcs = target.find("TexCoordList").findall("textureCoordinates");
            assert(len(tcs) == 1)
            tc = tcs[0];
            texCoords = [float(x) for x in tc.text.split(" ")];
            #print(uri, targetUri);
            textures[targetUri] = {"uri":uri, "coords":texCoords};

    #print (textures)

    polys = [];

    for i in bldg.iter("Polygon"):
        assert( i.find("interior") == None);
        assert( len(i.findall("exterior")) == 1)
        ext = i.find("exterior");
        assert(len(ext.findall("LinearRing")) == 1);
        ring = ext.find("LinearRing");
        pl = ring.find("posList").text;
        #print(pl);
        pl = [ float(x) for x in pl.split(" ")];

        # project coordinates from local EPSG:25833 to the widespread WSG 84 lat/lng
        for j in range( int(len(pl)/3)):
            x = pl[j*3];
            y = pl[j*3+1];
            latlng = proj(x, y, inverse=True);
            #print(latlng);
            pl[j*3] = latlng[1];
            pl[j*3+1]=latlng[0];


        pid = i.attrib["id"]
    #    print (i, pid);
        poly = {};
        poly["pid"] = pid;
        poly["coords"] = pl;
        if pid in textures:
            tex = textures[pid];
    #        print(tex);
            assert( len(tex["coords"]) % 2 == 0 and len(pl) % 3 == 0 and 
                     len(tex["coords"])/2 == len(pl)/3);
                     
            poly["texName"] = tex["uri"]
            poly["texCoords"] = tex["coords"]
        
        polys.append(poly);
    return polys;


for i in range(19464)[2:]:
    filename = 'buildings/bldg'+str(i);
    #print("reading file", filename+".xml");

    if i % 1000 == 0:
        print( str(int(i/1000))+ "k buildings converted");

    f = open(filename+".xml", 'rb')
    s = str(f.read(), "utf-8")
    f.close()

    #remove namespaces for easier parsing
    s = re.sub("<\w*:", "<", s);
    s = re.sub("</\w*:", "</", s);
    s = s.replace("gml:id", "id");
    s = s.replace("xlink:href", "href");
    
    #fOut = open("tmp.xml", "wb");
    #fOut.write( bytes(s, "utf-8"));
    #fOut.close();
    #print(s);
    
    bldg = ET.fromstring(s).find("Building");

    try:
        geo = getGeometry(bldg);
    except:
        print("building", i, "too complex, skipping");
        continue;

    asJson = json.dumps(geo, sort_keys=True, indent=4, separators=(',', ': '));
    
    fOut = open(filename+".json", "wb");
    fOut.write( bytes(asJson, "utf-8"));
    fOut.close();


