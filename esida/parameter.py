import os
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import geopandas

from dbconf import get_engine, connect

engine = get_engine()

meta_df = pd.read_csv('./input/meta_data/DB_Meta_Sheet - Documentation.csv')

meta_dict = meta_df[['Abbreviation', 'Category', 'Title']].set_index('Abbreviation').to_dict('index')

class BaseParameter():
    """ Base class for all parameters, implementing necessary functions. """

    def __init__(self):
        self.parameter_id = self.__class__.__name__
        self.rows = []
        self.logger = logging.getLogger('root')

    def get_title(self) -> str:
        if self.parameter_id in meta_dict:
            return meta_dict[self.parameter_id ]['Title']
        return self.parameter_id

    def get_category(self) -> str:
        if self.parameter_id in meta_dict:
            return meta_dict[self.parameter_id ]['Category']
        return '-'

    def get_data_path(self) -> Path:
        return Path(f"./input/data/{self.parameter_id}/")

    def get_output_path(self, name) -> Path:
        return Path(f"./output/{name}/{self.parameter_id}/")

    def get_fields(self, only_numeric=False):
        """ Check if the parameter has been loaded to the database. """
        sql = f"SELECT column_name, data_type \
            FROM information_schema.columns \
 WHERE table_schema = 'public' \
   AND table_name   = '{self.parameter_id}';"

        con = connect()
        res = con.execute(sql)
        fields = []
        for row in res:
            field = row[0]
            dtype = row[1]

            # if we want only numeric types for charts etc. filter out+
            # text based columns
            if only_numeric and dtype in ['text']:
                continue

            if field in ['index', 'year', 'date', 'shape_id']:
                continue

            fields.append(field)

        return fields


    def save(self):
        df = pd.DataFrame(self.rows)
        #df.to_csv('wtf.csv')
        df.to_sql(self.parameter_id, get_engine(), if_exists='replace')


    # ---

    def extract(self):
        """ (E)xtract: automatic download of source files. """
        pass

    def transform(self):
        """ (T)ransform: prepare data for loading. """
        pass

    def load(self, save_output=False):
        """ (L)oad: consume/calculate data to insert into data warehouse. """
        pass

    # ---

    def is_loaded(self) -> bool:
        """ Check if the parameter has been loaded to the database. """
        sql = f"SELECT EXISTS ( \
        SELECT FROM \
            pg_tables \
        WHERE \
            schemaname = 'public' AND \
            tablename  = '{self.parameter_id}' \
        );"

        con = connect()
        res = con.execute(sql)
        return res.fetchone()[0]


    def download(self, shape_id, start=None, end=None) -> pd.DataFrame:
        """ Download data for given shape id. """

        self.logger.debug("Downloading for shape_id=%s", shape_id)

        if not self.is_loaded():
            self.logger.warning("Download of data requested but not loaded for shape_id=%s", shape_id)
            return pd.DataFrame

        sql = f"SELECT * FROM {self.parameter_id} WHERE shape_id = {int(shape_id)}"

        if start:
            sql += f" AND year >= {start.year}"
        if end:
            sql += f" AND year <= {end.year}"

        df = pd.read_sql_query(sql, con=get_engine())

        if len(df) == 0:
            self.logger.warning("Download of data requested, is loaded, but empty for shape_id=%s", shape_id)
            return df

        # all parameters tables have index and shape id columns, drop them
        # always so we don't duplicate them while merging the DataFrames
        df = df.drop(['index','shape_id'], axis=1, errors='ignore')


        return df
    # ---

    def _get_shapes_from_db(self):
        """ Fetch all available districts and regions from the database. """

        sql = "SELECT * FROM shape WHERE type IN('region', 'district')"
        #sql = "SELECT * FROM shape WHERE name = 'Mjini'"

        gdf = geopandas.GeoDataFrame.from_postgis(
            sql,
            get_engine(), geom_col='geometry')
        shapes = []
        for _, row in gdf.iterrows():
            shapes.append({
                'id':       row['id'],
                'name':     row['name'],
                'geometry': row['geometry'],
            })

        if len(shapes) == 0:
            raise ValueError("No shapes found in database.")

        return shapes


    def _save_url_to_file(self, url, folder=None) -> bool:
        """ Downloads a URL to be saved on the parameter data directory.
        Checks if file has already been downloaded. Return True in case
        file was downloaded/was already downloaded, otherwise False.
        """
        a = urlparse(url)
        file_name = os.path.basename(a.path)

        if folder is None:
            folder = self.get_data_path()

        if os.path.isfile(folder / file_name):
            self.logger.debug("Skipping b/c already downloaded %s", url)
            return True

        try:
            subprocess.check_output(['wget', url, "-P", folder])
            return True
        except subprocess.CalledProcessError as error:
            self.logger.warning("Could not download file: %s, %s", url, error.stderr)

        return False

