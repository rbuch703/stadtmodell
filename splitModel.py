#! /usr/bin/python3

from os import remove;
import re;

f = open('Mitte/Mitte.gml', 'rb')

outputIdx = 0;

fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb")

for row_raw in f.readlines():
    row = str(row_raw, "utf-8")
    if row[:2] != "  ":
        continue;
    
    #remove namespaces from element names
    row = re.sub("<\w*:", "<", row);
    row = re.sub("</\w*:", "</", row);
    #remove leading two spaces, and remove namespaces from attribute names
    row = row[2:].replace("gml:id", "id").replace("xlink:href", "href");

    if "<cityObjectMember" in row:
        fOut.close()
        outputIdx+=1;
        fOut = open("buildings/bldg" + str(outputIdx) + ".xml", "wb");
        
        if outputIdx % 1000 == 0:
            print( str(int(outputIdx/1000))+ "k buildings extracted");

    fOut.write(bytes(row, "utf-8"));

# file 0 contains gml header data, and no building information
remove("buildings/bldg0.xml");
    
