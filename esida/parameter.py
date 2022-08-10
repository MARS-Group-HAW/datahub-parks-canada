import os
from sys import platform
import datetime as dt
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text
import pandas as pd
import geopandas

from dbconf import get_engine, connect

engine = get_engine()

meta_df = pd.read_csv('./input/meta_data/DB_Meta_Sheet - Documentation.csv')

meta_dict = meta_df[['Abbreviation', 'Category', 'Title', 'ESIDA database unit']].set_index('Abbreviation').to_dict('index')

class BaseParameter():
    """ Base class for all parameters, implementing necessary functions. """

    def __init__(self):
        self.parameter_id = self.__class__.__name__
        self.rows = []
        self.df = None
        self.logger = logging.getLogger('root')

        self.output_path = None

        self.time_col = 'year'

        self.output = 'db'

        # How many decimal digits should be displayed?
        # Only used in UI for human on the web, API and CSV data are never rounded
        self.precision = 3

        # Is the parameter a percentage?
        self.is_percent = False

        # If true the value range for the percentage is 0 to 100 instead of
        # 0 to 1
        self.is_percent100 = False

        self.da_temporal_start = dt.datetime(2010, 1, 1)
        self.da_temporal_end   = dt.datetime(2020, 12, 31)


    def get_title(self) -> str:
        if self.parameter_id in meta_dict:
            return meta_dict[self.parameter_id ]['Title']
        return self.parameter_id

    def get_category(self) -> str:
        if self.parameter_id in meta_dict:
            return meta_dict[self.parameter_id ]['Category']
        return '-'


    def get_unit(self) -> str:
        if self.parameter_id not in meta_dict:
            return ""

        unit =  meta_dict[self.parameter_id ]['ESIDA database unit']

        if unit == 'percent':
            return '%'

        if unit == 'None':
            return ''

        return unit

    def get_data_path(self) -> Path:
        return Path(f"./input/data/{self.parameter_id}/")

    def get_raw_data_size(self) -> int:
        """ get input data (raw data) size in bytes for parameter.
        depends on du cli utility so only works on linux systems.
        we use du for performance reasons, since collecting these stats with
        python would require looping over all the stored files. """
        if not self.get_data_path().exists():
            return 0

        if platform == "linux":
            return int(subprocess.check_output(['du', "-sb", self.get_data_path().as_posix()]).split()[0].decode('utf-8'))

        # du returns the amount of 512b chunks used by the file. So we need to
        # multiply with 512 to get the actual size in bytes.
        return int(subprocess.check_output(['du', "-s", self.get_data_path().as_posix()]).split()[0].decode('utf-8')) * 512


    def get_output_path(self) -> Path:

        if self.output_path is None:
            raise ValueError("You need to set the output path first.")

        return self.output_path

    def set_output_path(self, out_dir):
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)
        self.output_path = out_dir
        #return Path(f"./output/{name}/{self.parameter_id}/")

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
        if self.df is None:
            self.df = pd.DataFrame(self.rows)

        if self.output == 'db':
            self.df.to_sql(self.parameter_id, get_engine(), if_exists='replace')
        elif self.output == 'fs':
            self.df.to_csv(self.get_output_path() / f'{self.parameter_id}.csv')
        else:
            raise ValueError(f"Unknown save option {self.output}.")

    # ---

    def da_temporal_expected(self):
        if self.time_col == 'year':
            return self.da_temporal_end.year - self.da_temporal_start.year + 1
        elif self.time_col == 'date':
            return (self.da_temporal_end - self.da_temporal_start).days
        else:
            return None

    def da_count_temporal(self, shape_id=None):

        if not self.is_loaded():
            return None

        if self.time_col == 'year':
            sql = f"SELECT COUNT(*) FROM {self.parameter_id} WHERE  year >= {self.da_temporal_start.year} AND year <= {self.da_temporal_end.year}"
        elif self.time_col == 'date':
            sql = f"SELECT COUNT(*) FROM {self.parameter_id} WHERE date >= '{self.da_temporal_start}' AND date <= '{self.da_temporal_end}'"
        else:
            return None

        if shape_id:
            sql += f" AND shape_id = {int(shape_id)}"

        res = connect().execute(sql)
        return res.fetchone()[0]

    def da_temporal_date_first(self, shape_id=None):
        if not self.is_loaded():
            return None

        if self.time_col == 'year':
            sql = f"SELECT year FROM {self.parameter_id} WHERE 1=1"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " ORDER BY year ASC LIMIT 1"
        elif self.time_col == 'date':
            sql = f"SELECT date FROM {self.parameter_id} WHERE 1=1"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " ORDER BY date ASC LIMIT 1"

        res = connect().execute(sql)
        row = res.fetchone()
        if row:
            return str(row[0])
        else:
            return None

    def da_temporal_date_last(self, shape_id=None):
        if not self.is_loaded():
            return None

        if self.time_col == 'year':
            sql = f"SELECT year FROM {self.parameter_id} WHERE 1=1"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " ORDER BY year DESC LIMIT 1"
        elif self.time_col == 'date':
            sql = f"SELECT date FROM {self.parameter_id} WHERE 1=1"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " ORDER BY date DESC LIMIT 1"
        else:
            return None

        res = connect().execute(sql)
        row = res.fetchone()
        if row:
            return str(row[0])
        else:
            return None

    def da_temporal_date_first_dt(self):
        date = self.da_temporal_date_first()

        if self.time_col == 'year':
            return f"{date}-01-01"

        return date

    def da_temporal_date_last_dt(self):
        date = self.da_temporal_date_last()

        if self.time_col == 'year':
            return f"{date}-12-31"

        return date

    def da_temporal(self, shape_id=None):
        """ Determine temporal completeness of data source. """

        if not self.is_loaded():
            return None

        if self.time_col == 'year':
            should = self.da_temporal_end.year - self.da_temporal_start.year + 1
            sql = f"SELECT year FROM {self.parameter_id} WHERE  year >= {self.da_temporal_start.year} AND year <= {self.da_temporal_end.year}"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " GROUP BY year ORDER BY year"
            df = pd.read_sql(sql, con=connect())
            have = len(df)

            return have / should
        elif self.time_col == 'date':
            should = (self.da_temporal_end - self.da_temporal_start).days
            sql = f"SELECT date FROM {self.parameter_id} WHERE date >= '{self.da_temporal_start}' AND date <= '{self.da_temporal_end}'"
            if shape_id:
                sql += f" AND shape_id = {int(shape_id)}"
            sql += " GROUP BY date ORDER BY date"
            df = pd.read_sql(sql, con=connect())
            have = len(df)

            return have / should

        return None

    def da_spatial(self, shape_id=None):
        return None


    # ---

    def extract(self):
        """ (E)xtract: automatic download of source files. """
        raise NotImplementedError

    def transform(self):
        """ (T)ransform: prepare data for loading. """
        raise NotImplementedError

    def load(self, save_output=False):
        """ (L)oad: consume/calculate data to insert into data warehouse. """
        raise NotImplementedError

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


    def download(self, shape_id=None, start=None, end=None) -> pd.DataFrame:
        """ Download data for given shape id. """

        self.logger.debug("Downloading for shape_id=%s", shape_id)

        if not self.is_loaded():
            self.logger.warning("Download of data requested but not loaded for shape_id=%s", shape_id)
            return pd.DataFrame

        sql = f"SELECT * FROM {self.parameter_id} WHERE 1=1"

        if shape_id:
            sql += f" AND shape_id = {int(shape_id)}"

        if self.time_col == 'year':
            if start:
                sql += f" AND year >= {start.year}"
            if end:
                sql += f" AND year <= {end.year}"
        elif self.time_col == 'date':
            if start:
                sql += f" AND date >= '{str(start)}'"
            if end:
                sql += f" AND date <= '{str(end)}'"
        else:
            raise ValueError(f"Unknown time_col={self.time_col}")

        df = pd.read_sql_query(sql, con=get_engine())

        if len(df) == 0:
            self.logger.warning("Download of data requested, is loaded, but empty for shape_id=%s", shape_id)
            return df

        # all parameters tables have index and shape id columns, drop them
        # always so we don't duplicate them while merging the DataFrames
        drop_cols = ['index']
        if shape_id:
            drop_cols.append('shape_id')
        df = df.drop(drop_cols, axis=1, errors='ignore')


        return df

    def peek(self, shape_id):
        """ Get the latest known value of the parameter, if available. """

        if not self.is_loaded():
            self.logger.warning("Peek of data requested but not loaded for shape_id=%s", shape_id)
            return None

        sql = f"SELECT * FROM {self.parameter_id} WHERE shape_id = {shape_id} ORDER BY {self.time_col} DESC LIMIT 1"

        con = connect()
        res = con.execute(sql)
        req = res.fetchone()

        if req is None:
            return None

        dreq =  dict(req)

        if self.parameter_id not in dreq:
            self.logger.error("Parameter column missing in peek for shape_id=%s", shape_id)
            return None

        if self.time_col not in dreq:
            self.logger.error("Time column missing in peek for shape_id=%s", shape_id)
            return None

        return dreq

    def format_value(self, value) -> str:

        if isinstance(value, (float)):
            if self.is_percent:
                if not self.is_percent100:
                    value = value * 100

            if self.precision is not None:
                value = round(value, self.precision)

        return value

    # ---



    def _get_shapes_from_db(self, id=None):
        """ Fetch all available districts and regions from the database. """

        sql = "SELECT * FROM shape WHERE type IN('region', 'district')"
        #sql = "SELECT * FROM shape WHERE name = 'Mjini'"

        if id:
            sql = "SELECT * FROM shape WHERE id = " + str(int(id))

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


    def _save_url_to_file(self, url, folder=None, file_name=None) -> bool:
        """ Downloads a URL to be saved on the parameter data directory.
        Checks if file has already been downloaded. Return True in case
        file was downloaded/was already downloaded, otherwise False.
        """
        a = urlparse(url)

        if file_name is None:
            file_name = os.path.basename(a.path)

        if folder is None:
            folder = self.get_data_path()

        if os.path.isfile(folder / file_name):
            self.logger.debug("Skipping b/c already downloaded %s", url)
            return True

        try:
            params = ['wget', "-O", folder / file_name, url]
            subprocess.check_output(params)
            return True
        except subprocess.CalledProcessError as error:
            self.logger.warning("Could not download file: %s, %s", url, error.stderr)

        return False

