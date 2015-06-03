#! /usr/bin/python3

f = open('/mnt/StadtmodellBerlin3D/Mitte/Mitte.gml', 'rb')

outputIdx = 1;

fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb")

for row in f.readlines():
    if "<cityObjectMember" in str(row, "utf-8"):
        fOut.close()
        outputIdx+=1;
        fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb");
        
        if outputIdx % 1000 == 0:
            print( str(int(outputIdx/1000))+ "k buildings extracted");

    fOut.write(row);
