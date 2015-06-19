#! /usr/bin/python3

from PIL import Image;
from math import ceil, log;
import json;
#import cairo;
import os;
import re;

# parses a geometryTile json file, extracts the list of all referenced texture files,
# and returns a list of those texture file names along with each texture's width and 
# height in pixels
def getTextureSizes( geometryTileFileName):
    data = json.loads( open(geometryTileFileName).read())
    
    textures = [];
    numPixels = 0;
    texSizes = [];

    for poly in data:
        texUri = poly["texUri"];
        if texUri :
            textures.append( texUri);
        
    textures = list(set(textures)); # 'set' to make unique, 'list' to be able to sort
    textures.sort();

    for texUri in textures:
        im = Image.open(texUri);
        size = list(im.size);
        
        size[0] = min( size[0], 512);
        size[1] = min( size[1], 512);
        
        if im.size[0] != size[0] or im.size[1] != size[1]:
            pass
            #print( "[WARN] reducing size of texture", texUri, "from", im.size, "to", size);
            
        texSizes.append( (size, texUri) );
        numPixels += (size[0] * size[1])
    
    return texSizes, numPixels;


# a measure of how useful the two residuals are: the more square-shaped both are,
# the better
def getSubdivisionQuality( res0, res1):
    # ratio of excentricity: 'longer edge'/'shorter edge'
    as0 = max(res0["width"], res0["height"]) / min(res0["width"], res0["height"])
    as1 = max(res1["width"], res1["height"]) / min(res1["width"], res1["height"])

    # aspect ratios weighted by pixel area
    return res0["width"] * res0["height"] * as0 + \
           res1["width"] * res1["height"] * as1

def getBinArea( theBin):    
    return theBin["width"] * theBin["height"]

# returns the (at most two) remaining unused areas that are created when an item of 
# 'itemSize' is put into the top-left corner of 'theBin':
#   ------------
#   |    |     |     bin = item+X+Y+Z
#   |item|  X  |     
#   ------------
#   |    |     |
#   | Y  |  Z  |
#   |    |     |
#   ------------
#
def getResiduals( theBin, itemSize):
    #binSize = getBinSize(theBin);
    #binX, binY = theBin;
    #binHeight = 
    
    binWidth  = theBin["width"]
    binHeight = theBin["height"]
    itemWidth, itemHeight = itemSize;
    assert( binWidth >= itemWidth and binHeight >= itemHeight);
    # case 1: item == bin, X == Y == Z == ∅ 
    if binWidth == itemWidth and binHeight == itemHeight: return (None, None)
    
    # case 2: item fills whole width --> X == Z == ∅ --> residual: (Y)
    if binWidth == itemWidth: 
        return ( {"left":  theBin["left"],
                  "top":   theBin["top"] + itemHeight, 
                  "width": binWidth,
                  "height":binHeight - itemHeight,
                  "atlas"   :theBin["atlas"]},
                   None);

    # case 3: item fills whole height --> Y == Z == ∅ --> residual: (X)
    if binHeight == itemHeight: ## --> unused area is right of item
        return ( {"left":  theBin["left"] + itemWidth,
                  "top":   theBin["top"],
                  "width": binWidth - itemWidth,
                  "height":binHeight,
                  "atlas"   :theBin["atlas"]},
                   None);
    
    residualArea = getBinArea(theBin) - (itemSize[0]*itemSize[1]);
    # general case X == Y == Z != ∅
    # candidate set 1:
    #   resA0 = Y
    #   resA1 = (X + Z)
    resA0 = { "left": theBin["left"],
              "top": theBin["top"] + itemHeight,
              "width":  itemWidth,
              "height": binHeight - itemHeight,
              "atlas"   :theBin["atlas"]}
              
    resA1 = { "left": theBin["left"] + itemWidth,
              "top":  theBin["top"],
              "width": binWidth - itemWidth, 
              "height":binHeight,
              "atlas"   :theBin["atlas"]}

    assert( getBinArea(resA0) + getBinArea(resA1) == residualArea);
    qA = getSubdivisionQuality( resA0, resA1);
    
    #candidate set 2:
    # resB0 = X
    # resB1 = (Y + Z)
    resB0 = { "left":   theBin["left"] + itemWidth,
              "top":    theBin["top"],
              "width":  binWidth - itemWidth, 
              "height": itemHeight,
              "atlas"   :theBin["atlas"]}
              
    resB1 = { "left": theBin["left"],
              "top": theBin["top"] + itemHeight,
              "width": binWidth,
              "height": binHeight - itemHeight,
              "atlas"   :theBin["atlas"]}
              
    assert( getBinArea(resB0) + getBinArea(resB1) == residualArea);
    qB = getSubdivisionQuality( resB0, resB1);

    return (resA0, resA1) if qA < qB else (resB0, resB1);

# attempts to find a suitable bin from 'bins' in which to pack 'item'
# if packing succeeds, the method modifies 'bins' to reflect the insertion and returns 
# the tile created that holds 'item'. Otherwise, nothing is modified and 'None' is returned
def tryPack(item, bins):
    #print("#", item)
    itemSize = item[0];
    itemWidth, itemHeight = itemSize;
    for i in range(len(bins)):
        if bins[i]["width"] < itemWidth or bins[i]["height"] < itemHeight:
            continue;
        #print( "will put item", item, "into bin", bins[i]);
        res0, res1 = getResiduals(bins[i], itemSize)
        tile = { "top":   bins[i]["top"], 
                 "left":  bins[i]["left"],
                 "width": itemWidth,
                 "height":itemHeight,
                 "srcUri":   item[1],
                 "atlas": bins[i]["atlas"]}
        bins[i] = bins[-1];
        bins.pop()
        if res0: bins.append(res0);
        if res1: bins.append(res1);
        return tile;
    
    return None;

def nextHigherPowerOfTwo(a):
    aOrig = a
    power = ceil( log(a)/log(2));
    
    res = 1 << power;
    assert( res >= aOrig and res < 2*aOrig)
    return res;

def getOptimalBinSize(texSizes):
    global MAX_ATLAS_WIDTH, MAX_ATLAS_HEIGHT;
    texelsLeft = sum([ x[0][0] * x[0][1] for x in texSizes])
    maxWidth = max( [x[0][0] for x in texSizes])
    maxHeight =max( [x[0][1] for x in texSizes])
    
    width = nextHigherPowerOfTwo(maxWidth)
    height= nextHigherPowerOfTwo(maxHeight)
    assert( width <= MAX_ATLAS_WIDTH and height <= MAX_ATLAS_HEIGHT)

    # try to make the new atlas bin big enough to fit the remaining tiles with as little
    # slack as possible. Since each loop iteration double the length of one texture edge
    # (to let textures keep power-of-two edges), the texture area double in every iteration.
    # - a FILL_RATIO of 1.0 would ensure an atlas size between 1x and 2x as big as needed,
    #   wasting considerable GPU memory
    # - a FILLRATION of 0.5 would ensure an atlas size between 0.5x and 1x as big as needed,
    #   wasting no space, but creating a lot of independent textures
    FILL_RATIO = 0.7;    
    while (width < MAX_ATLAS_WIDTH or height < MAX_ATLAS_HEIGHT) and (width*height < FILL_RATIO*texelsLeft):
        if width < height:
            width *= 2;
        else:
            height *= 2;
    
    if width < 256: width = 256;
    if height < 256: height = 256;
            
    assert( width <= MAX_ATLAS_WIDTH and height <= MAX_ATLAS_HEIGHT)
    
    #print(texelsLeft, maxWidth, maxHeight, width, height)
    return width, height
    #exit(0);
    

def binPack(texSizes, atlasBaseName):
    numBins = 0;
    bins = []
    tiles = [];
    
    while len(texSizes) > 0:
        size = getOptimalBinSize(texSizes);
        # there wasn't enough space left --> need to create an additional atlas file
        # and try again
        newBin = {"top": 0, "left":0, "width": size[0], "height": size[1], 
                  "atlas": { "width": size[0], 
                             "height":size[1], 
                             "uri": atlasBaseName + "_" + str(numBins) + ".jpg"
                           }
                 }
        #print("creating new atlas file '" + newBin["uri"] + "'");
        numBins += 1;
        bins.append(newBin);

        for texIdx in range(len(texSizes)):
            item = texSizes[texIdx];
            bins.sort( key=lambda x: x["width"] * x["height"], reverse=False);
            tile = tryPack(item, bins);
            
            if tile:
                texSizes[texIdx] = None;
                tiles.append(tile);
                
        texSizes = [x for x in texSizes if x != None];

    print("geometry tile", atlasBaseName, "has", numBins, "atlas textures")
    return bins, tiles

def createAtlas(tiles):
    
    atlases = {tile["atlas"]["uri"]: tile["atlas"] for tile in tiles}
    
    texelsUsed = 0;
    for atlasUri in atlases:
        atlas = atlases[atlasUri]
        atlasImg = Image.new("RGB", [atlas["width"], atlas["height"]])
        for tile in [x for x in tiles if x["atlas"] == atlas]:
            texelsUsed += tile["width"] * tile["height"];
           
            srcImg = Image.open( tile["srcUri"])
            size = list(srcImg.size);
            
            size[0] = min( size[0], 512);
            size[1] = min( size[1], 512);
            
            if srcImg.size[0] != size[0] or srcImg.size[1] != size[1]:
                #print( "[WARN] reducing size of texture", tile["uri"], "from", srcImg.size, "to", size);
                srcImg = srcImg.resize( size, Image.LANCZOS);
            
            assert( srcImg.size[0] == tile["width"] and srcImg.size[1] == tile["height"])
            atlasImg.paste( srcImg, (tile["left"], tile["top"]))

        atlasImg.save(atlas["uri"], quality=90, optimize=True); # subsampling=0

        atlasImg = atlasImg.resize([ atlas["width"] >> 1, atlas["height"] >> 1]);
        atlasImg.save(atlas["uri"]+".half", quality=90, optimize=True, format="JPEG");

        atlasImg = atlasImg.resize([ atlas["width"] >> 2, atlas["height"] >> 2]);
        atlasImg.save(atlas["uri"]+".quarter", quality=90, optimize=True, format="JPEG");
        
        
    return texelsUsed;

#def createAtlasPdf(tiles, bins):
#    surface = cairo.PDFSurface("map.pdf", ATLAS_WIDTH, ATLAS_HEIGHT);
#    ctx = cairo.Context (surface);
#    ctx.set_line_width (1/2000)
#    for tile in tiles:
#        ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); 
#        ctx.set_source_rgba(1, 0, 0, 0.5);
#        ctx.fill_preserve();
#
#        ctx.set_source_rgb(0, 0, 0);
#        ctx.stroke();
#
#    for tile in bins:
#        ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); 
#        ctx.set_source_rgba(0, 0, 1, 0.5);
#        ctx.fill_preserve();
#
#        ctx.set_source_rgb(0, 0, 0);
#        ctx.stroke();
#
#    surface.finish();
#    surface.flush();

def createAtlasBasedGeometryTile( inputFileName, outputFileName, tiles):
    #global ATLAS_WIDTH, ATLAS_HEIGHT
    f = open(inputFileName, "rb")
    polys = json.loads( str(f.read(), "utf8"))
    f.close()
    
    atlases = {tile["atlas"]["uri"]: tile["atlas"] for tile in tiles}
    #atlases = set( tile["atlasUri"] for tile in tiles);
    res = [];
    
    
    geometry = {};
    #print(polys);
    #exit(0);
    #for tile in tiles:
    #    print(tile);
        
    atlases = {tile["atlas"]["uri"]: tile["atlas"] for tile in tiles}
    tiles = { tile["srcUri"] : tile for tile in tiles}
    
    for atlasUri in atlases:
        atlas = atlases[atlasUri]
        atlasGeometry = [];
        for poly in [x for x in polys if "texUri" in x and x["texUri"] in tiles and tiles[x["texUri"]]["atlas"] == atlas]:
            assert(poly["texUri"] in tiles)
            tile = tiles[poly["texUri"]] # look up where this polygon's texture has been mapped to
            assert( tile["atlas"] == atlas)
#                continue;
             
            del poly["texUri"];   
            
            for pos in poly["outer"]:
                # clamp s and t to [0.0, 1.0]
                s = max(min(pos[3], 1.0), 0.0);
                # CityGML seems to store texture coordinates with the positive t-axis going up,
                # while OpenGL uses the opposite convention. So while we are touching texture
                # coordinates, convert this convention as well
                t = max(min(1-pos[4], 1.0), 0.0);
                pos[3] =  (tile["left"] + s * tile["width"]) / atlas["width"];
                pos[4] =  (tile["top"] + t * tile["height"]) / atlas["height"];
                #print( pos[3], pos[4]);
                assert (pos[3] <= 1.0 and pos[4] <= 1.0)

            for ring in poly["inner"]:
                for pos in ring:
                    s = max(min(pos[3], 1.0), 0.0);
                    # convert t-coordinate from CityGML to OpenGL convention, same as above
                    t = max(min(1-pos[4], 1.0), 0.0);
                    pos[3] =  (tile["left"] + s * tile["width"]) / atlas["width"];
                    pos[4] =  (tile["top"] + t * tile["height"]) / atlas["height"];
                    assert (pos[3] <= 1.0 and pos[4] <= 1.0)
            atlasGeometry.append(poly)
        geometry[atlasUri] = atlasGeometry;
        #print(poly)
    
    # We deleted the "texUri" from all polygons that are mapped to atlas textures.
    # This should leave us only with those polygons without a texture
    untexturedGeometry = [];
    for poly in [x for x in polys if "texUri" in x]:
        assert( poly["texUri"] == None);
        del poly["texUri"];
        untexturedGeometry.append(poly);

    geometry[None] = untexturedGeometry;        
        
    open(outputFileName, "wb").write( bytes(json.dumps(geometry), "utf8"))


##### main #####

# maximum guaranteed supported resolution of WebGL is 2048x2048
MAX_ATLAS_WIDTH = 2048
MAX_ATLAS_HEIGHT= 2048
INPUT_DIR = "tiles";
OUTPUT_DIR = "atlas";

if INPUT_DIR[-1]  not in ["/", "\\"]: INPUT_DIR += "/";
if OUTPUT_DIR[-1] not in ["/", "\\"]: OUTPUT_DIR+= "/";

files = list(os.listdir(INPUT_DIR));
files.sort();

for filename in files:
#for filename in ["70417_42985.json"]:
    m = re.match("^(\\d+)_(\\d+).json$", filename)
    if not m:
        continue

    x = m.group(1);
    y = m.group(2);
    
    #print(x,y)
    #exit(0);
    os.makedirs( OUTPUT_DIR + str(x), exist_ok = True);
    #fileBase = filename[:-5]
    #print(fileBase)
    #continue;
        
    texSizes, numPixels = getTextureSizes( INPUT_DIR + filename)
    texSizes.sort( key=lambda x: x[0][0]*x[0][1], reverse=True);
    bins, tiles = binPack(texSizes, OUTPUT_DIR + str(x) + "/" + str(y))

    texelsUsed = createAtlas(tiles);
    #createAtlasPdf(tiles, bins);

    createAtlasBasedGeometryTile(INPUT_DIR+filename, OUTPUT_DIR + str(x) + "/" + str(y) + ".json", tiles)
    #print("Texels used: ", texelsUsed/1000, "k")



