#! /usr/bin/python3

import json;
import math;
import os;

def mergeBoundingBoxes(a, b):
    return { 
        "top":    min(a["top"],    b["top"]),
        "bottom": max(a["bottom"], b["bottom"]),
        "left":   min(a["left"],   b["left"]),
        "right":  max(a["right"],  b["right"])
    }

def getRingBoundingBox(ring):
    return { 
        "top":    min( [x[0] for x in ring]),
        "bottom": max( [x[0] for x in ring]),
        "left":   min( [x[1] for x in ring]),
        "right":  max( [x[1] for x in ring])
    }
    
def getPolygonBoundingBox(poly):
    bb = getRingBoundingBox( poly["outer"]);
    for innerRing in poly["inner"]:
        bb = mergeBoundingBoxes(bb, getRingBoundingBox(innerRing))
    return bb

# taken from http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = (lon_deg + 180.0) / 360.0 * n
    ytile = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
    return (xtile, ytile)
  
def getTilesCovered(bbox, level):
    x1, y1 = deg2num( bbox["bottom"], bbox["left"], level);
    x2, y2 = deg2num( bbox["top"], bbox["right"], level);
    
    assert(x1 <= x2 and y1 <= y2)
    
    res = [];
    for x in range( int(x1), int(x2)+1):
        res += [ (x, y) for y in range( int(y1), int(y2)+1)]
            
    return res;    

tileData = {}

for i in range(1,19463):
    if i % 1000 == 0:
        print( str(int(i/1000)) + "k buildings read");
    geom = json.loads( open("geometry/bldg"+str(i)+".json").read());
    for polygon in geom:
        #print(polygon);
        bbox = getPolygonBoundingBox(polygon);
        tiles = getTilesCovered(bbox, 17);
        
        for tilePos in tiles:
            if tilePos not in tileData:
                tileData[tilePos] = [];
            tileData[tilePos].append(polygon);

print("writing tiles");

for tile in tileData:
    print (tile, len(tileData[tile]))
    os.makedirs( "tiles/", exist_ok=True)# + str(tile[0]))
    #f = open( "tiles/"+str(tile[0]) + "/" + str(tile[1]) + ".json")
    f = open( "tiles/"+str(tile[0]) + "_" + str(tile[1]) + ".json", "wb")
    f.write( bytes(json.dumps(tileData[tile]), "utf8"));
    f.close()


