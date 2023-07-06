# What you need to know if you want to use the Data Hub in another geographic area

1. Fork and clone either the [ESIDA](https://github.com/MARS-Group-HAW/esida-db) or the [Parks Canada](https://github.com/MARS-Group-HAW/datahub-parks-canada) GitHub repository. If you are unsure how to do it please see a nice tutorial by the [W3C](https://www.w3schools.com/git/git_remote_fork.asp?remote=github).

2. The Data Hub (DH) currently supports three hierarchy levels within the selected area of interest. In the case of Parks Canada, this are the following: Country, Province, and Conservation area. You'll need one [Shapefile](https://en.wikipedia.org/wiki/Shapefile) or [GeoPackage](https://www.geopackage.org/) for each level.  
Web portals providing open geodata are widely spread. In the case here we used the sources as follows:  
	A. [Canada's administrative boundaries](https://public.opendatasoft.com/explore/dataset/world-administrative-boundaries/table/)  
	B. [Canada's provinces](https://public.opendatasoft.com/explore/dataset/georef-canada-province-millesime/table/?disjunctive.prov_name_en)  
	C. [Canada's national parks](https://hub.arcgis.com/datasets/dd8cd91871534c9aa34310eed84fe076/explore?location=59.996604%2C-96.810200%2C5.14)  
Of course, similar data can be found on different portals, here you have to gain some experience yourself.  
The folders with the shapefiles and additional data are stored in the `input/shapes` folder.  

3. The following is about harmonizing the attribute tables of the GIS data and merging them into a GeoPackage. For this purpose a script is provided, which can be edited and executed with [Jupyter Notebook](https://jupyter.org/). This can be found at [https://github.com/MARS-Group-HAW/datahub-parks-canada/notebooks/Data Hub Prepare Canada Shapes.ipynb](https://github.com/MARS-Group-HAW/datahub-parks-canada/blob/main/notebooks/Data%20Hub%20Prepare%20Canada%20Shapes.ipynb).
