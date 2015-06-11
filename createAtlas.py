#! /usr/bin/python3

from PIL import Image;
import json;
import cairo;

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
        while (size[0] > 512 or size[1] > 512):
            if size[0] > 1: size[0] >>= 1;
            if size[1] > 1: size[1] >>= 1;
        
        if im.size[0] != size[0] or im.size[1] != size[1]:
            print( "[WARN] reducing size of texture", texUri, "from", im.size, "to", size);
            
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
                  "uri"   :theBin["uri"]},
                   None);

    # case 3: item fills whole height --> Y == Z == ∅ --> residual: (X)
    if binHeight == itemHeight: ## --> unused area is right of item
        return ( {"left":  theBin["left"] + itemWidth,
                  "top":   theBin["top"],
                  "width": binWidth - itemWidth,
                  "height":binHeight,
                  "uri"   :theBin["uri"]},
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
              "uri"   :theBin["uri"]}
              
    resA1 = { "left": theBin["left"] + itemWidth,
              "top":  theBin["top"],
              "width": binWidth - itemWidth, 
              "height":binHeight,
              "uri"   :theBin["uri"]}

    assert( getBinArea(resA0) + getBinArea(resA1) == residualArea);
    qA = getSubdivisionQuality( resA0, resA1);
    
    #candidate set 2:
    # resB0 = X
    # resB1 = (Y + Z)
    resB0 = { "left":   theBin["left"] + itemWidth,
              "top":    theBin["top"],
              "width":  binWidth - itemWidth, 
              "height": itemHeight,
              "uri"   :theBin["uri"]}
              
    resB1 = { "left": theBin["left"],
              "top": theBin["top"] + itemHeight,
              "width": binWidth,
              "height": binHeight - itemHeight,
              "uri"   :theBin["uri"]}
              
    assert( getBinArea(resB0) + getBinArea(resB1) == residualArea);
    qB = getSubdivisionQuality( resB0, resB1);

    return (resA0, resA1) if qA < qB else (resB0, resB1);

# attempts to find a suitable bin from 'bins' in which to pack 'item'
# if packing succeeds, the method modifies 'bins' to reflect the insertion and returns 
# the tile created that holds 'item'. Otherwise, nothing is modified and 'None' is returned
def tryPack(item, bins):
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
                 "uri":   item[1]}
        bins[i] = bins[-1];
        bins.pop()
        if res0: bins.append(res0);
        if res1: bins.append(res1);
        return tile;
    
    return None;


def binPack(texSizes, bins):
    tiles = [];
    for item in texSizes:
        bins.sort( key=lambda x: x["width"] * x["height"], reverse=False);
        tile = tryPack(item, bins);

        if tile: 
            tiles.append(tile);
        else: 
            assert(false)
    
    return bins, tiles

def createAtlas(tiles):
    global ATLAS_WIDTH, ATLAS_HEIGHT
    atlas = Image.new("RGB", [ATLAS_WIDTH, ATLAS_HEIGHT])
    texelsUsed = 0;
    for tile in tiles:
        texelsUsed += tile["width"] * tile["height"];
       
        srcImg = Image.open( tile["uri"])
        size = list(srcImg.size);
        
        while (size[0] > 512 or size[1] > 512):
            if size[0] > 1: size[0] >>= 1;
            if size[1] > 1: size[1] >>= 1;
        
        if srcImg.size[0] != size[0] or srcImg.size[1] != size[1]:
            #print( "[WARN] reducing size of texture", tile["uri"], "from", srcImg.size, "to", size);
            srcImg = srcImg.resize( size, Image.LANCZOS);
        
        assert( srcImg.size[0] == tile["width"] and srcImg.size[1] == tile["height"])
        atlas.paste( srcImg, (tile["left"], tile["top"]))

    atlas.save("atlas.jpg", quality=90, optimize=True); # subsampling=0
    return texelsUsed;

def createAtlasPdf(tiles, bins):
    surface = cairo.PDFSurface("map.pdf", ATLAS_WIDTH, ATLAS_HEIGHT);
    ctx = cairo.Context (surface);
    ctx.set_line_width (1/2000)
    for tile in tiles:
        ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); 
        ctx.set_source_rgba(1, 0, 0, 0.5);
        ctx.fill_preserve();

        ctx.set_source_rgb(0, 0, 0);
        ctx.stroke();

    for tile in bins:
        ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); 
        ctx.set_source_rgba(0, 0, 1, 0.5);
        ctx.fill_preserve();

        ctx.set_source_rgb(0, 0, 0);
        ctx.stroke();

    surface.finish();
    surface.flush();



##### main #####

ATLAS_WIDTH = 4096
ATLAS_HEIGHT= 4096

bins = [{"top": 0, "left":0, "width": ATLAS_WIDTH, "height": ATLAS_HEIGHT, 
         "uri": "atlas/70415_42974.jpg"}]
texSizes, numPixels = getTextureSizes("tiles/70415_42974.json")
texSizes.sort( key=lambda x: x[0][0]*x[0][1], reverse=True);
bins, tiles = binPack(texSizes, bins)

texelsUsed = createAtlas(tiles);
createAtlasPdf(tiles, bins);

print("Texels used: ", texelsUsed/1000, "k")



