import os
import datetime as dt
from pathlib import Path
import importlib
import pkgutil

import logging

import click
import pandas as pd
import geopandas
from meteostat import Stations, Daily

import esida.statcompiler as stc
from dbconf import get_engine
import log


logger = log.setup_custom_logger('root')

@click.group()
def cli():
    pass

@cli.command()
def init():
    """ Init database, by creating database and importing district/region shapes. """

    # regions first, so foreign-keys exist
    regions_gdf = geopandas.read_file('./input/shapes/Districts_Shapefiles_2019/Regions based on Districts.shp')
    regions_gdf = regions_gdf.rename(columns={
        "Region_Nam": "name",
        "Region_Cod": "region_code",
    })
    regions_gdf['type'] = 'region'
    regions_gdf = regions_gdf.sort_values(by=['region_code'])
    regions_gdf.to_postgis('shape', get_engine(), if_exists='append')

    imported_regions_gdf = geopandas.GeoDataFrame.from_postgis("SELECT * FROM shape WHERE type= 'region'", get_engine(), geom_col='geometry')

    def find_pk_if_region(name):
        for i, row in imported_regions_gdf.iterrows():
            if (row['name'] == name):
                return row['id']
        raise ValueError(f"No parent region id found for region ({name})")

    districts_gdf = geopandas.read_file('./input/shapes/Districts_Shapefiles_2019/Districts and TC as 2020 FIXED.shp')
    districts_gdf = districts_gdf.rename(columns={
        "NewDist20":  "name",
        "Region_Nam": "region_name",
        "Region_Cod": "region_code",
        "District_C": "district_c"
    })
    districts_gdf['type'] = 'district'
    districts_gdf['parent_id'] = districts_gdf['region_name'].apply(find_pk_if_region)
    districts_gdf = districts_gdf.sort_values(by=['region_code', 'district_c'])
    districts_gdf.to_postgis('shape', get_engine(), if_exists='append')

    # calculate district area
    # Date are in ESPG:4326 (deg based), so for ST_Area() to produce m2
    # we need to convert to a meters based system. With utmzone() we identify
    # the resp. used UTM Zone that is m based.
    engine = get_engine()
    with engine.connect() as con:
        con.execute('UPDATE shape SET area_sqm = \
          ST_Area(ST_Transform(geometry, utmzone(ST_Centroid(geometry))))')


@cli.command()
@click.option('-p', '--parameter', default=None, type=str)
def extract(parameter):
    """ Download input from sources to local store. """
    params  = ['worldpop_poverty', 'worldpop_popc', 'worldpop_popd',
    'worldpop_urbanext', 'chc_chirps']

    if parameter is not None:
        params = [parameter]

    for p in params:
        logger.info(f"Calling EXTRACT for parameter {p}")
        pm = importlib.import_module(f'parameters.{p}')
        pm.extract()


@cli.command()
@click.option('-p', '--parameter', default=None, type=str)
def transform(parameter):
    """ Download input from sources to local store. """
    params  = ['tza_hfr']

    if parameter is not None:
        params = [parameter]

    for p in params:
        logger.info("Calling TRANSFORM for parameter %s", p)
        pm = importlib.import_module(f'parameters.{p}')
        pm.transform()

@cli.command()
@click.option('-p', '--parameter', default=None, type=str)
def load(parameter):
    """ Download input from sources to local store. """
    params  = ['tza_hfr']

    if parameter is not None:
        params = [parameter]

    for p in params:
        logger.info("Calling LOAD for parameter %s", p)
        pm = importlib.import_module(f'parameters.{p}')
        pm.load()


@cli.command("list")
def list_parameters():
    """ Print all available parameters. """
    parameters  = [name for _, name, _ in pkgutil.iter_modules(['parameters'])]

    for parameter in parameters:
        print(parameter)

@cli.command()
@click.argument('parameter')
@click.argument('action')
def param(parameter, action):
    params  = [name for _, name, _ in pkgutil.iter_modules(['parameters'])]

    if parameter not in params:
        click.echo(click.style('Unknown parameter',  fg='red'), err=True)
        return

    pmodule = importlib.import_module(f'parameters.{parameter}')
    pclass  = getattr(pmodule, parameter)()
    result = getattr(pclass, action)()

@cli.command()
@click.option('-p', '--parameter', default=None, type=str)
@click.option('-s', '--shape', default=None, type=str)
@click.option('--dry-run', default=False, is_flag=True)
def regiontiffs(parameter, shape, dry_run):
    """ Import locally prepared regional GeoTiffs with individual logic. """

    params  = ['worldpop_urbanext', 'worldpop_popd', 'worldpop_popc', 'worldpop_poverty', 'malariaatlas_incidence', 'chc_chirps']
    if parameter is not None:
        params = [parameter]

    engine  = get_engine()
    outputs = sorted(os.listdir("./output/"))

    cwd = os.getcwd()
    df = pd.read_sql_query('SELECT id, name FROM district', con=engine)

    # loop over all defined parameters
    for p in params:
        pm = importlib.import_module('parameters.{}'.format(p))

        rows = []

        for _, row in df.iterrows():
            # reconstruct output folder name
            shape_out_dir = os.path.join(cwd, 'output', row['name'])

            if shape is not None and shape != row['name']:
                continue

            if not os.path.isdir(shape_out_dir):
                continue

            param_dir = os.path.join(shape_out_dir, p)

            if os.path.isdir(param_dir):
                # multiple files per parameter for multiple years
                files = sorted([s for s in os.listdir(param_dir) if s.rpartition('.')[2] in ('tiff','tif')])
                print(files)
                for f in files:
                    s  = pm.consume(os.path.join(param_dir, f), district_id=row['id'])
                    s['district_id'] = row['id']

                    rows.append(s)
                    print("\t{} - ".format(f) + str(s))
            else:
                print("no feature for {}".format(shape))

        if not dry_run:
            pm.to_sql(rows, engine)
        else:
            print(rows)
            print("Dry-run, not writing to database.")

@cli.command()
@click.option('-p', '--parameter', default=None, type=str)
def statcompiler(parameter):
    """ Import statcompiler sources. """

    engine  = get_engine()
    outputs = sorted(os.listdir("./output/"))

    params  = ['statcompiler_education']
    if parameter is not None:
        params = [parameter]

    regions_df = pd.read_sql_query('SELECT region_id, name FROM region ORDER by name', con=engine)

    for p in params:
        pm = importlib.import_module(f'parameters.{p}')

        df = stc.fetch_from_stat_compiler(pm.indicators)

        # safe raw data
        output_dir = Path(f'input/data/{p}/')
        output_file = '{}_data_{}.csv'.format(dt.datetime.today().strftime('%Y-%m-%d_%H-%M-%S'), p)
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_dir / output_file, index=False)

        # cleanup data
        # remove the generic / zone admin levels and only leave regions
        df['is_region'] = df['CharacteristicLabel'].apply(stc.is_region)
        df = df[df['is_region'] == True]

        df['CharacteristicLabel'] = df['CharacteristicLabel'].apply(stc.normalize_region_name)
        df['CharacteristicLabel'] = df['CharacteristicLabel'].apply(stc.map_region_name_to_tz_stat_names)

        # group
        df = stc.group_per_studyyear_region(df, pm.indicators, regions_df)

        # statcompiler specific data wrangling
        df = pm.compute(df)

        pm.to_sql(df, engine)


@cli.command()
def meteostat():
    """ Fetch meteostat stations and data. """

    # Database access
    engine  = get_engine()

    # fetch Meteostat weather stations for TZ
    stations = Stations()
    stations = stations.region('TZ')
    print('Stations in Tanzania:', stations.count())

    df = stations.fetch()

    # Meteostat ID is not always numerical. Safe the internal Meteostat ID
    # but add an numerical index for smooth PostGis access
    df['meteostat_id'] = df.index
    df.insert(0, 'meteostat_id', df.pop('meteostat_id')) # move meteostat ID to second column (directly ≤after index)

    df['id'] = range(1, len(df)+1)
    df.insert(0, 'id', df.pop('id'))

    gdf = geopandas.GeoDataFrame(
        df, geometry=geopandas.points_from_xy(df.longitude, df.latitude))


    gdf.to_postgis("meteostat_stations", engine, if_exists='replace')


    # loop over all stations and collect daily values
    start = dt.datetime(2000, 1, 1)
    end = dt.datetime(2021, 3, 31)

    dfs = []

    for i, row in gdf.iterrows():
        print("Fetching {} ({})".format(row['name'], row['meteostat_id']))
        data = Daily(row['meteostat_id'], start, end)
        data = data.fetch()

        print("Found {} rows".format(len(data)))
        data['meteostat_station_id'] = row['id']
        dfs.append(data)

    merged_df = pd.concat(dfs)
    merged_df.to_sql("meteostat_data", engine, if_exists='replace')



if __name__ == '__main__':
    cli()
