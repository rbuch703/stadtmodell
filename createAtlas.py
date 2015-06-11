#! /usr/bin/python3

from PIL import Image;
import json;
import cairo;

data = json.loads( open("tiles/70415_42974.json").read())

textures = [];

for poly in data:
    texUri = poly["texUri"];
    if texUri :
        textures.append( texUri);
        
textures = list(set(textures)); # 'set' to make unique, 'list' to be able to sort
textures.sort();

texSizes = []

numPixels = 0

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

texSizes.sort( key=lambda x: x[0][0]*x[0][1], reverse=True);

def getSubdivisionQuality( res0, res1):
    as0 = max(res0["width"], res0["height"]) / min(res0["width"], res0["height"])
    as1 = max(res1["width"], res1["height"]) / min(res1["width"], res1["height"])
    #print("aspects:", as0, as1)

    # aspect ratios weighted by pixel area
    return res0["width"] * res0["height"] * as0 + \
           res1["width"] * res1["height"] * as1

#def getBinSize( theBin):
#    x,y = theBin;
#    assert ( x[0] < x[1] and y[0] < y[1])
#    return ( x[1]-x[0], y[1] - y[0])
def getBinArea( theBin):    
    return theBin["width"] * theBin["height"]

def getResiduals( theBin, itemSize):
    #binSize = getBinSize(theBin);
    #binX, binY = theBin;
    #binHeight = 
    
    binWidth  = theBin["width"]
    binHeight = theBin["height"]
    itemWidth, itemHeight = itemSize;
    assert( binWidth >= itemWidth and binHeight >= itemHeight);
    if binWidth == itemWidth and binHeight == itemHeight: return (None, None)
    if binWidth == itemWidth: #item fills whole width
        return ( {"left":  theBin["left"],
                  "top":   theBin["top"] + itemHeight, 
                  "width": binWidth,
                  "height":binHeight - itemHeight},
                   None);

                   
    if binHeight == itemHeight: ##item fills whole height
        return ( {"left":  theBin["left"] + itemWidth,
                  "top":   theBin["top"],
                  "width": binWidth - itemWidth,
                  "height":binHeight},
                   None);

    resA0 = { "left": theBin["left"],
              "top": theBin["top"] + itemHeight,
              "width":  itemWidth,
              "height": binHeight - itemHeight}
              
              
    resA1 = { "left": theBin["left"] + itemWidth,
              "top":  theBin["top"],
              "width": binWidth - itemWidth, 
              "height":binHeight}
    #print(resA0);
    #print(resA1);
    #print(theBin);
    assert( itemSize[0]*itemSize[1] + getBinArea(resA0) + getBinArea(resA1) == getBinArea(theBin));
    qA = getSubdivisionQuality( resA0, resA1);
    
    resB0 = { "left":   theBin["left"] + itemWidth,
              "top":    theBin["top"],
              "width":  binWidth - itemWidth, 
              "height": itemHeight}
              
    resB1 = { "left": theBin["left"],
              "top": theBin["top"] + itemHeight,
              "width": binWidth,
              "height": binHeight - itemHeight}
    assert( itemSize[0]*itemSize[1] + getBinArea(resB0) + getBinArea(resB1) == getBinArea(theBin));

    qB = getSubdivisionQuality( resB0, resB1);
    
    #print(qA, qB);
    
    return (resA0, resA1) if qA < qB else (resB0, resB1);

ATLAS_WIDTH = int(1 * 4096)
ATLAS_HEIGHT= 4096;

tiles = [];
bins = [{"top": 0, "left":0, "width": ATLAS_WIDTH, "height": ATLAS_HEIGHT},
#        {"top": 0, "left":0, "width": 2048, "height": 1024}
]

print("numTexels:", bins[0]["width"] * bins[0]["height"])

#print (bins);

for item in texSizes:
    #print("#",item);
    itemSize = item[0];
    itemWidth, itemHeight = itemSize;
    put = False;
    
    bins.sort( key=lambda x: x["width"] * x["height"], reverse=False);
    
    for i in range(len(bins)):
        #print("bin: ",bins[i]);
        #binSize = getBinSize(bins[i]);
        #print(boxSize, binSize);
        if bins[i]["width"] >= itemWidth and bins[i]["height"] > itemHeight:
            #print( "will put item", item, "into bin", bins[i]);
            tiles.append( { "top":   bins[i]["top"], 
                          "left":  bins[i]["left"],
                          "width": itemWidth,
                          "height":itemHeight,
                          "uri":   item[1]})
            res0, res1 = getResiduals(bins[i], itemSize)
            #print(res0, res1);
            bins[i] = bins[-1];
            bins.pop()
            if res0: bins.append(res0);
            if res1: bins.append(res1);
            put = True
            break;
    if not put:
        print("no space for", item)
        assert(False);
            
#print(bins);
atlas = Image.new("RGB", [ATLAS_WIDTH, ATLAS_HEIGHT])


texelsUsed = 0;
for tile in tiles:
    texelsUsed += tile["width"] * tile["height"];
   
    srcImg = Image.open( tile["uri"])
    size = list(srcImg.size);
    print("================")
    print(tile);
    print(tile["uri"], size);
    print(size);
    while (size[0] > 512 or size[1] > 512):
        if size[0] > 1: size[0] >>= 1;
        if size[1] > 1: size[1] >>= 1;
    
    if im.size[0] != size[0] or im.size[1] != size[1]:
        print( "[WARN] reducing size of texture", texUri, "from", im.size, "to", size);
        srcImg = srcImg.resize( size, Image.LANCZOS);
    
    
    assert( srcImg.size[0] == tile["width"] and srcImg.size[1] == tile["height"])
    atlas.paste( srcImg, (tile["left"], tile["top"]))

atlas.save("atlas.jpg", quality=90, optimize=True); # subsampling=0

print("Texels used: ", texelsUsed/1000, "k")

surface = cairo.PDFSurface("map.pdf", ATLAS_WIDTH, ATLAS_HEIGHT);
ctx = cairo.Context (surface);
ctx.set_line_width (1/2000)
#ctx.set_source_rgb(0.0, 0.0, 0.0);

#ctx.set_line_width (1)

#    ctx.rectangle(lngMin, latMin, lngMax - lngMin, latMax - latMin);
for tile in tiles:
    ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); #x, y, width, height
    ctx.set_source_rgba(1, 0, 0, 0.5);
    ctx.fill_preserve();

    ctx.set_source_rgb(0, 0, 0);
    ctx.stroke();

for tile in bins:
    ctx.rectangle( tile["left"], tile["top"], tile["width"], tile["height"]); #x, y, width, height
    ctx.set_source_rgba(0, 0, 1, 0.5);
    ctx.fill_preserve();

    ctx.set_source_rgb(0, 0, 0);
    ctx.stroke();
    

#ctx.scale(500, -500);
#ctx.translate(1, -1);

surface.finish();
surface.flush();

#print(tiles)

#for size in texSizes:
#    print (size, size[0][0]*size[0][1] / 1000)
#print(str(numPixels/1000000) + "M")

