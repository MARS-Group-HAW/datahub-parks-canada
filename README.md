# ESIDA DB Pipeline

## Usage

### Extract data for MARS ABM

After ingesting data you can create the MARS ABM box for an arbitrary region inside the area of the imported data.

    $ python ./eisda-cli.py clip --wkt <path to WKT Polygon> --abm

This will generate a simulation blueprint with the required input data.


## Setup

### Local setup (Docker)

Clone the repository.

Copy the `.env` file and make sure it's correct populated.

    $ cp .env.example .env

For the local data to the needed destination (this is to pre-fill the persistent data mount needed in Kubernetes):

    $ rsync -a input/data.local/ input/data/

If you need to run the MARS ABM, store the zip files of the boxes inside `./input/dat/MARS/`.

Build and start the containers:

    $ docker-compose up -d

After this you can start/stop the containers with

    $ docker-compose start|stop

The ESIDA DB is available at [http://localhost/](http://localhost/) - though it is empty at the moment
and not everything works. To set it up follow these steps:

Enter the Docker container (Docker GUI CLI or `$ docker-compose exec esida bash`) and run the following commands.
Those are only required to be run after the first setup.

    $ flask create-db          # setup required database columns
    $ python esida-cli.py init # import region/district shape files into db

After that you can load the different parameters by key into the database:

    $ python ./esida-cli.py param <key> extract # downloads files from source
    $ python ./esida-cli.py param <key> load    # processes source and saves to datab

For example to load Meteostat weather data:

    $ python ./esida-cli.py param meteo_tprecit extract
    $ python ./esida-cli.py param meteo_tprecit load

For available parameters see the listing at [http://localhost/parameter](http://localhost/parameter). After loading, you can use the download function for each shape or use the API to get the data (see Jupyter Notebook in folder `./notebooks/ESIDA DB Demo.ipynb`).


### Local development (directly)

Stat the PostGIS database with docker-compose as shown above. Then install the dependencies:

- PostGIS (you use the one from docker-compose: `$ docker-compose up -d postgis`)
- GDAL
- Python 3.9.x
- Python packages with `$ pip install -r requirements.txt`
- Make local ESIDA Python package: `$ pip install -e .`
- Make the Flask App know to the system: `$ export FLASK_APP=esida`
- Run gunicorn to serve flask App: `$ gunicorn --bind 0.0.0.0:80 esida:app --error-logfile - --reload`
- Page can now be access via http://localhost/


### HAW ICC Deployment

Create Kubernetes space:

    $ kubectl apply -f ./k8s/space-esida.yaml

Access for further HAW users can be added with the `k8s/rolebinding.yaml`.

Create PersistentVolumeClaim's (PVC) for permanent storage independent of container life-cycle:

    $ kubectl apply -f ./k8s/pvc-postgis.yaml        # Storage of PostGis database
    $ kubectl apply -f ./k8s/pvc-esidadb-input.yaml  # Storage of input data of the pipeline
    $ kubectl apply -f ./k8s/pvc-esidadb-output.yaml # Storage of output files (per district files i.e.)

Create Service and Deployment for PostGIS database and ESIDA DB pipeline/flask app:


Login to the pods:

    $ kubectl exec -it <Name des Pods> -n <space-name> -- bash
    $ kubectl exec -it $(kubectl -n esida get pod | grep esida-db | awk '{ print $1 }') -n esida -- bash

Port forwarding to access pod:e

    $ kubectl port-forward <pod> -n esida 8432:80

    $ kubectl port-forward $(kubectl -n esida get pod | grep postgis | awk '{ print $1 }') -n esida 6432:5432


Get logs

    $ kubectl logs $(kubectl -n esida get pod | grep esida-db | awk '{ print $1 }') -n esida


Delete something

    $ kubectl delete -f ./k8s/<file.yaml>

Debugging:

    $ kubectl describe pods -n esida # might hint deploymentment issues

Download files from pod:

    $ tar -zcvf <name>.tar.gz <folder>/ # create archive of data in pod
    $ kubectl cp esida/<some-pod>:/app/<name>.tar.gz ./ # run from your host
