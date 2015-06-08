#! /usr/bin/python3

import re;
import json;
import xml.etree.ElementTree as ET
import pyproj;

#proj = pyproj.Proj("+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs");
proj = pyproj.Proj(init="epsg:25833");

def parseTextures(bldg, filename):
    textures = [];
    sdmRefs = [];
    for i in bldg.iter("appearance"):
        assert( len(i.findall("Appearance")) == 1)
        appr = i.find("Appearance");
        theme = appr.find("theme").text;

        #print("Appearance");
        for sdm in appr.iter("surfaceDataMember"):
            #print("\tsdm");
            if not len(sdm): #the surfaceDataMember has no children --> is just a reference
                assert("href" in sdm.attrib);
                href = sdm.attrib["href"];
                assert( href[0] == "#");

                if theme == "rgbTexture":
                    sdmRefs.append( href[1:]);
                #print("empty sdm", sdm, sdm.attrib);
                continue;
            
            # the surfaceDataMember has children: either a texture or a material
            assert(len(sdm.attrib) == 0)
            assert(len(sdm) == 1);
            child = sdm[0];
            assert(child.tag in ("ParameterizedTexture", "X3DMaterial"));
            
            if child.tag == "X3DMaterial":
                if theme == "rgbTexture":
                    print("[warn] untextured surface in textured model", filename);
                continue;
            
            assert( child.tag == "ParameterizedTexture");
            texNode = child;
            
            texId = texNode.attrib["id"];
            if theme == "rgbTexture":
                sdmRefs.append(texId);
            
            uri = texNode.find("imageURI").text

            tex = { "id": texId, "imageUri": uri, "targets":[]}

            for target in texNode.findall("target"):
                targetUri = target.attrib["uri"]
                assert(targetUri[0] == "#")
                targetUri = targetUri[1:]
                
                targetNode = {"ref": targetUri, "texCoords":[]}
                #print("\t\tsdm2")    
                assert( len(target) == 1)
                for texCoords in target[0].findall("textureCoordinates"):
                    assert( "ring" in texCoords.attrib);
                    targetId = texCoords.attrib["ring"];
                    tcs = [float(x) for x in texCoords.text.split(" ")];
                    assert( len(tcs) % 2 == 0);
                    targetNode["texCoords"].append( {"subRef": targetId, "texCoords": tcs} );
                    
                tex["targets"].append(targetNode);
            
            textures.append(tex);
            #assert(len(tcs) == 1)
            #tc = tcs[0];
            ##print(uri, targetUri);
            #textures[targetUri] = {"uri":uri, "coords":texCoords};
    sdmRefs = set(sdmRefs);
    #print("refs:")#, sdmRefs);
    #for ref in sdmRefs:
    #    print("\t", ref);
    #print("textures:")#, textures);
    #for tex in textures:
    #    print("\t", tex["id"]);
    #print("len before:", len(textures));
    textures = [ tex for tex in textures if tex["id"] in sdmRefs];   
    return textures;
    #print("len after:", len(textures));
    #exit(0);
    #print (textures)
    #print(sdmRefs);


def getGeometry(bldg, filename):
    global proj;
    textures = {};
    #sdms = [];
    
    polys = [];
    return textures, [];
    
    
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
    return textures, polys;


for i in range(1,19463):
#for i in [9225,]:
    filename = 'buildings/bldg'+str(i);
    #print("reading file", filename+".xml");

    if i % 1000 == 0:
        print( str(int(i/1000))+ "k buildings converted");

    f = open(filename+".xml", 'rb')
    s = str(f.read(), "utf-8")
    f.close()

   
    #fOut = open("tmp.xml", "wb");
    #fOut.write( bytes(s, "utf-8"));
    #fOut.close();
    #print(s);
    
    bldg = ET.fromstring(s).find("Building");

    try:
        textures = parseTextures(bldg, filename);
#        textures, geo = getGeometry(bldg, filename);
    except Exception as e:
        print("in file", filename, e)
#        print( e);
        raise;
    #    print("building", i, "too complex, skipping");
    #    continue;

    #print(textures)
    #asJson = json.dumps(textures, sort_keys=True, indent=4, separators=(',', ': '));
    #fOut = open("tmp.json", "wb");
    #fOut.write( bytes(asJson, "utf-8"));
    #fOut.close();


