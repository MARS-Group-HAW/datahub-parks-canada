# build and start docker containers
docker-compose up -d

# drop database and delete all data
docker-compose exec esida flask drop-db

# create database
docker-compose exec esida flask create-db

# import fundamental GIS files into database
docker-compose exec esida python ./esida-cli.py load-shapes ./input/shapes/Canada_overview.gpkg

# download and process precipitation data from Meteostat
docker-compose exec esida python ./esida-cli.py param meteo_tprecit extract
docker-compose exec esida python ./esida-cli.py param meteo_tprecit load


