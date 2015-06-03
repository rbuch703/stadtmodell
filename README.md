# stadtmodell

This repository contains basic tools to process data from the "3D Stadtmodell Berlin"
* `splitModel.py`: Splits a CityGML input file into individual files for each building for easier processing. Note: while having the extension `.xml`, the created files are not valid XML files in the strict sense, as they contain namespaced entities without containing the corresponding namespace declarations.
* `parseBuildings.py`: parses each building XML file created using `splitModel.py`, and writes the extracted relevant geometry information (3D geometry, texture coordinates, texture names) to an output JSON file.

Dependencies:
* needs `pyproj` for Python3 (e.g. package `python3-pyproj` for Ubuntu)
