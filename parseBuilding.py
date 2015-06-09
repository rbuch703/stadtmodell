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
                    print("[warn] untextured surface in textured model in building", filename);
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
                
                targetNode = {"ref": targetUri, "subTargets":[]}
                #print("\t\tsdm2")    
                assert( len(target) == 1)
                for texCoords in target[0].findall("textureCoordinates"):
                    assert( "ring" in texCoords.attrib);
                    targetId = texCoords.attrib["ring"];
                    assert(targetId[0] == "#")
                    tcs = [float(x) for x in texCoords.text.split(" ")];
                    tcTuples = [];
                    assert( len(tcs) % 2 == 0);
                    for j in range( int(len(tcs)/2)):
                        tcTuples.append( (tcs[2*j], tcs[2*j+1]) );
                    targetNode["subTargets"].append( {"subRef":    targetId[1:], 
                                                      "texCoords": tcTuples} );
                    
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

def parseRing( linearRingElement):
    #print (linearRingElement, linearRingElement.attrib)
    assert( "id" in linearRingElement.attrib);
    ringId = linearRingElement.attrib["id"];
    posList = linearRingElement.find("posList");
    assert( "srsDimension" in posList.attrib);
    assert( posList.attrib["srsDimension"] == "3");
    verts = [ float(x) for x in posList.text.split(" ")];
    vertsNew = [];
    # project coordinates from local EPSG:25833 to the widespread WSG 84 lat/lng
    for j in range( int(len(verts)/3)):
        x = verts[j*3];
        y = verts[j*3+1];
        latlng = proj(x, y, inverse=True);
        #print(latlng);
        #verts[j*3] = latlng[1];
        #verts[j*3+1]=latlng[0];
        vertsNew.append( (latlng[1], latlng[0], verts[j*3+2]));
        
    
    return {"id": ringId, "vertices": vertsNew};

def getGeometry(bldg, filename):
    global proj;
    textures = {};
    
    polys = {};
   
    
    for i in bldg.iter("Polygon"):
        assert( "id" in i.attrib);
        polyId = i.attrib["id"];
        poly = {"inner":[]};
        assert( len(i.findall("exterior")) == 1)
        ext = i.find("exterior");
        assert(len(ext.findall("LinearRing")) == 1);
        poly["outer"] = parseRing( ext.find("LinearRing") )
        #assert( i.find("interior") == None);
        
        for inner in i.findall("interior"):
            assert(len(inner.findall("LinearRing")) == 1);
            poly["inner"].append( parseRing(inner.find("LinearRing")));
            
        #print(poly);
        #exit(0);
        #print(pl);


    #    print (i, pid);
        #if pid in textures:
        #    tex = textures[pid];
        #    assert( len(tex["coords"]) % 2 == 0 and len(pl) % 3 == 0 and 
        #             len(tex["coords"])/2 == len(pl)/3);
        #    poly["texName"] = tex["uri"]
        #    poly["texCoords"] = tex["coords"]
        
        assert( not polyId in polys)
        polys[polyId] = poly;
        #polys.append(poly);
    return polys;

def integrateRing( geomRing, texRing, filename ):
    #print("IR");
    #print(texRing);

    if len(texRing) == len(geomRing["vertices"]):
        # normal case: there is a texCoord tuple for each vertex
        # convert (lat, lng, z) and (s, t) ==> (lat, lng, z, s, t)
        return [ a[0] + a[1] for a in zip( geomRing["vertices"], texRing)];

    print("[WARN] mismatch of #vertices <-> #texCoords in surface", geomRing["id"], 
          "in building", filename)

    #print(geomRing);
    #print(len(texRing), len(geomRing["vertices"]))
    #assert(False);
    return pseudoIntegrateRing(geomRing);


def integratePolygon( texUri, texId, texTarget, polygon, filename):
    assert("texUri" not in polygon)
    polygon["texUri"] = texUri;
    
    #assert( texTarget["ref"] = polygon["
    targets = { subTarget["subRef"] : subTarget["texCoords"] for subTarget in texTarget["subTargets"]}
    
    #print (texUri, "\n\n", targets, "\n\n", polygon, "\n")
    #print (polygon["outer"]["id"])
    assert( polygon["outer"]["id"] in targets)
    #outer = ;

    innerRings = [];
    
    for inner in polygon["inner"]:
        if inner["id"] in targets:
            innerRings.append( integrateRing( inner, targets[inner["id"]], filename))
        else:
            print("[WARN] in building", filename,
                  ": texture", texId, "references surface", texTarget["ref"], "but does not supply texture coordinates for child ring", inner["id"]);
            innerRings.append( pseudoIntegrateRing( inner));
#            exit(0);
            
    return { "texUri" : texUri,
             "outer": integrateRing( polygon["outer"], targets[polygon["outer"]["id"]], filename),
             "inner": innerRings
             }
    #print("\n", outer, innerRings)
    #exit(0)

def pseudoIntegrateRing( ring):
    return [ (x[0], x[1], x[2], 0, 0) for x in ring["vertices"] ]
    #print(ring);
    #exit(0);
    #pass
    
def pseudoIntegratePolygon( polygon ):
    return {
        "texUri": None,
        "outer": pseudoIntegrateRing( polygon["outer"]),
        "inner": [ pseudoIntegrateRing( x ) for x in polygon["inner"]]
        }

def integrate(geometry, textures, filename):
    res = []
    for tex in textures:
        for target in tex["targets"]:
            targetRef = target["ref"]
            #print("texture", tex["id"], "has target", );
            if not targetRef in geometry:
                print("[WARN] texture", tex["id"], "references non-existing target", targetRef,
                      "in building", filename)
                continue
                
            res.append(integratePolygon( tex["imageUri"], tex["id"], target, geometry[targetRef], filename));
            del geometry[targetRef];    # has been merged --> remove from todo-list
    
    # At this point, all entries left in 'geometry' are not referenced by any texture.
    # To be able to render them anyway we add dummy texture coordinates and a 'null'
    # texture to each.
    # Note: usually, those are GroundSurfaces, for which to texture could be recorded
    # TODO: tag each surface with its type (ground, wall, roof), and throw warnings only when
    #       an untextured surface is not a ground surface
    #       Alternative: ignore groud surfaces completely when initially parsing the geometry
    for untexturedPolygon in geometry:
        #print("[WARN] surface", untexturedPolygon,"in",filename, "has no associated texture")
        res.append( pseudoIntegratePolygon( geometry[untexturedPolygon]));

    return res;
        

    

PATH = 'buildings/'
for i in range(1,19463):
#for i in [9455]:
    filename = PATH + 'bldg'+str(i);
    #print("reading file", filename+".xml");

    if i % 1000 == 0:
        print( str(int(i/1000))+ "k buildings converted");

    f = open(filename+".xml", 'rb')
    s = str(f.read(), "utf-8")
    f.close()
   
    bldg = ET.fromstring(s).find("Building");
    buildingId = bldg.attrib["id"]

    try:
        textures = parseTextures(bldg, buildingId);
        geometry = getGeometry(bldg, buildingId);
        res = integrate(geometry, textures, buildingId);
    except Exception as e:
        print("in file", filename, e)
#        print( e);
        raise;
    #    print("building", i, "too complex, skipping");
    #    continue;

    #print(textures)
    #asJson = json.dumps(geometry, sort_keys=True, indent=4, separators=(',', ': '));
    #fOut = open("geom.json", "wb");
    #asJson = json.dumps(textures, sort_keys=True, indent=4, separators=(',', ': '));
    #fOut = open("tmp.json", "wb");
    #fOut.write( bytes(asJson, "utf-8"));
    #fOut.close();
    
    asJson = json.dumps(res);
    fOut = open("geometry/bldg"+str(i)+".json", "wb");
    fOut.write( bytes(asJson, "utf-8"));
    fOut.close();



