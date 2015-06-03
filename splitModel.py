#! /usr/bin/python3

f = open('/mnt/StadtmodellBerlin3D/Mitte/Mitte.gml', 'rb')

outputIdx = 1;

fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb")

for row in f.readlines():
    if "<bldg:Building gml:id" in str(row, "utf-8"):
        fOut.close()
        outputIdx+=1;
        fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb");


        
    fOut.write(row);
    #r = str(row, "utf-8")[:-2]
    #print (r)
