#! /usr/bin/python3

import re;
import json;
import xml.etree.ElementTree as ET
import pyproj;
import os;
import hashlib;

#proj = pyproj.Proj("+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs");
proj = pyproj.Proj(init="epsg:25833");

digests = {}
texUris = set();

def parseTextures(bldg, filename):
    global digests, texUris;
    textures = [];
    sdmRefs = [];
    for i in bldg.iter("appearance"):
        assert( len(i.findall("Appearance")) == 1)
        appr = i.find("Appearance");
        theme = appr.find("theme").text;

        #print("Appearance");
        for sdm in appr.iter("surfaceDataMember"):
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
            assert("id" in child.attrib);
            
            if child.tag == "X3DMaterial":
                if theme == "rgbTexture":
                    print(ESC_FG_YELLOW+"[WARN] untextured surface", child.attrib["id"],
                          "in textured model in building", filename, ESC_RESET);
                continue;
            
            assert( child.tag == "ParameterizedTexture");
            texNode = child;
            
            texId = texNode.attrib["id"];
            if theme == "rgbTexture":
                sdmRefs.append(texId);
            
            uri = texNode.find("imageURI").text
            
            #print(uri);
            if not os.path.isfile(uri):
                print(ESC_FG_RED+"[ERR ] texture file", uri, "for texture", texId, "in building", filename, "does not exist", ESC_RESET);
                #exit(0);
                continue;
            
            
            m = hashlib.md5()
            m.update( open(uri, "rb").read())
            dig = m.digest()
            
            if not dig in digests:
                digests[dig] = uri
            elif uri != digests[dig]:
                #print("[WARN] identical textures", uri, "and", digests[dig]);
                uri = digests[dig]


                
            #exit(0);
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
                        tcTuples.append( [tcs[2*j], tcs[2*j+1]] );
                    targetNode["subTargets"].append( {"subRef":    targetId[1:], 
                                                      "texCoords": tcTuples} );
                    
                tex["targets"].append(targetNode);
            
            textures.append(tex);
    sdmRefs = set(sdmRefs);

    textures = [ tex for tex in textures if tex["id"] in sdmRefs];   
    return textures;


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
        z = verts[j*3+2];
        latlng = proj(x, y, inverse=True);
        #print(latlng);
        #verts[j*3] = latlng[1];
        #verts[j*3+1]=latlng[0];
        vertsNew.append( [latlng[1], latlng[0], z]);
        
    
    return {"id": ringId, "vertices": vertsNew};

def getMinHeight(polygon):
    minHeight = min ( [x[2] for x in polygon["outer"]["vertices"]] )
    for inner in polygon["inner"]:
        minHeight = min ( minHeight, min( [x[2] for x in inner["vertices"] ]));

    return minHeight;

def biasHeight(polygon, heightBias):
        
    #print(minHeight)
    for i in range(len(polygon["outer"]["vertices"])):
        polygon["outer"]["vertices"][i][2] += heightBias

    for inner in polygon["inner"]:
        for i in range(len(inner["vertices"])):
            inner["vertices"][i][2] += heightBias

def getGeometry(bldg, filename):
    global proj;
    textures = {};
    
    polys = {};
    
    # parse LOD3 geometry if present, otherwise fall back to LOD2
    surfaceContainers = bldg.iter("lod3MultiSurface") if len(bldg.findall("lod3MultiSurface")) else bldg.iter("lod2MultiSurface");
    
    for lod2MultiSurface in surfaceContainers:
        for i in lod2MultiSurface.iter("Polygon"):
            assert( "id" in i.attrib);
            polyId = i.attrib["id"];
            poly = {"inner":[]};
            assert( len(i.findall("exterior")) == 1)
            ext = i.find("exterior");
            assert(len(ext.findall("LinearRing")) == 1);
            poly["outer"] = parseRing( ext.find("LinearRing"))
            #assert( i.find("interior") == None);
            
            for inner in i.findall("interior"):
                assert(len(inner.findall("LinearRing")) == 1);
                poly["inner"].append( parseRing(inner.find("LinearRing")))
                
            assert( not polyId in polys)
            polys[polyId] = poly;
    
    if len(polys) == 0:
        return {};
        
    minHeight = min([ getMinHeight(polys[i]) for i in polys])
    for i in polys:
        biasHeight( polys[i], -minHeight);

    minHeight = min([ getMinHeight(polys[i]) for i in polys])
    return polys;

def integrateRing( geomRing, texRing, filename ):

    #print("##", type(geomRing["vertices"]), type(texRing))
    #print(list(zip( geomRing["vertices"], texRing)));
    if len(texRing) == len(geomRing["vertices"]):
        # normal case: there is a texCoord tuple for each vertex
        # convert (lat, lng, z) and (s, t) ==> (lat, lng, z, s, t)
        return [ a[0] + a[1] for a in zip( geomRing["vertices"], texRing)];

    print(ESC_FG_RED+"[ERR ] mismatch of #vertices <-> #texCoords in surface", geomRing["id"], 
          "in building", filename, ESC_RESET)

    return pseudoIntegrateRing(geomRing);


def integratePolygon( texUri, texId, texTarget, polygon, filename):
    assert("texUri" not in polygon)
    polygon["texUri"] = texUri;
    
    targets = { subTarget["subRef"] : subTarget["texCoords"] for subTarget in texTarget["subTargets"]}
    assert( polygon["outer"]["id"] in targets)

    innerRings = [];
    
    for inner in polygon["inner"]:
        if inner["id"] in targets:
            innerRings.append( integrateRing( inner, targets[inner["id"]], filename))
        else:
            print("[ERR ] in building", filename,
                  ": texture", texId, "references surface", texTarget["ref"], "but does not supply texture coordinates for child ring", inner["id"]);
            innerRings.append( pseudoIntegrateRing( inner));
            
    return { "texUri" : texUri,
             "outer": integrateRing( polygon["outer"], targets[polygon["outer"]["id"]], filename),
             "inner": innerRings
             }

def pseudoIntegrateRing( ring):
    return [ (x[0], x[1], x[2], 0, 0) for x in ring["vertices"] ]
    
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
                #print("[WARN] texture", tex["id"], "references non-existing target", targetRef,
                #      "in building", filename)
                continue
                
            res.append(integratePolygon( tex["imageUri"], tex["id"], target, geometry[targetRef], filename));
            del geometry[targetRef];    # has been merged --> remove from todo-list
    
    # At this point, all entries left in 'geometry' are not referenced by any texture.
    # To be able to render them anyway we add dummy texture coordinates and a 'null'
    # texture to each.
    # Note: usually, those are GroundSurfaces, for which no texture could be recorded
    # TODO: tag each surface with its type (ground, wall, roof), and throw warnings only when
    #       an untextured surface is not a ground surface
    #       Alternative: ignore ground surfaces completely when initially parsing the geometry
    for untexturedPolygon in geometry:
        #print("[WARN] surface", untexturedPolygon,"in",filename, "has no associated texture")
        res.append( pseudoIntegratePolygon( geometry[untexturedPolygon]));

    return res;
        

TEXTURE_INPUT_DIR = "./"
#if TEXTURE_INPUT_DIR[-1] not in ["/", "\\"]: TEXTURE_INPUT_DIR+= "/";
#
#dirs = list(os.listdir( TEXTURE_INPUT_DIR+"appearance/"))
#for dir_ in dirs:
#    if not os.path.isdir(dir_):
#        continue
#        
#    for file_ in os.listdir( TEXTURE_INPUT_DIR+"appearance/"+dir_):
#        fileName = TEXTURE_INPUT_DIR+"appearance/"+dir_+"/" + file_;
#        if not os.path.isfile(fileName):
#            continue
#        textureFiles.append( fileName)
#    print(dir_);
#exit(0);

ESC_FG_YELLOW = "\033[33m";
ESC_FG_RED = "\033[31m";
ESC_RESET =  "\033[0m";


PATH = 'buildings/'

#for i in [1726]:
buildings = {};
i = 1;

files = list([x for x in os.listdir(PATH)]);
files.sort();

for filename in files:
    if i % 1000 == 0:
        print( str(int(i/1000))+ "k buildings converted");

    f = open(PATH + filename, 'rb')
    s = str(f.read(), "utf-8")
    f.close()
   
    bldg = ET.fromstring(s).find("Building");
    
    buildingId = bldg.attrib["id"]
    if buildingId in buildings:
        print(ESC_FG_YELLOW+ "[WARN] building", buildingId, "is present multiple times (", filename, "and", buildings[buildingId], "). Will ignore all but the first occurence.",ESC_RESET);
        i+=1;
        continue;
    else:
        buildings[buildingId] = filename;
        
    try:
        textures = parseTextures(bldg, buildingId);
        geometry = getGeometry(bldg, buildingId);
        res = integrate(geometry, textures, buildingId);
    except Exception as e:
        print("in file", filename, e)
        raise;
   
    asJson = json.dumps(res);
    fOut = open("geometry/" + filename[:-3]+"json", "wb");
    fOut.write( bytes(asJson, "utf-8"));
    fOut.close();
    
    i+=1



