# stadtmodell

This repository contains basic tools to process data from the "3D Stadtmodell Berlin"
* `splitModel.py`: Splits a CityGML input file into individual files for each building for easier processing. 
* `parseBuildings.py`: parses each building's XML file created using `splitModel.py`, and writes the extracted relevant geometry information (3D geometry, texture coordinates, texture names) to an output JSON file.
* `createTiles.py`: converts the geometry from a set of parsed building JSON files (those created by `parseBuildings.py`) to a set of geometry tiles with each tile covering a particular geographic area. Tile sizes and boundaries are chosen as to correspond to the widely-used [slippy map tilenames](http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames) convention.

Dependencies:
* needs `pyproj` for Python3 (e.g. package `python3-pyproj` for Ubuntu)
