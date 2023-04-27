from pathlib import Path

import pandas as pd

from esida.parameter import BaseParameter

from dbconf import get_engine

class tnbs_medlabdens(BaseParameter):

    def __init__(self):
        super().__init__()

    def get_data_path(self) -> Path:
        return Path("./input/data/tnbs_disthealthworkers/")

    def extract(self):
        # Nothing to do here, manually prepared excel file, extracted from
        # 2012 census
        pass

    def load(self, shapes=None, save_output=False):

        # load regions ids
        sql = "SELECT id, name FROM shape WHERE type IN('region')"
        gdf = pd.read_sql(sql, get_engine())
        name_to_id = dict(zip(gdf.name, gdf.id))

        def normalize_name(name):
            if name == 'Dar-es-salaam':
                name = 'Dar es salaam'
            return name.upper()

        # load data
        df = pd.read_csv(self.get_data_path() / 'Distribution of all health workers.csv')
        df_total = pd.read_csv(self.get_data_path() / 'Distribution of health workers densities.csv')

        rows = []

        for name, shape_id in name_to_id.items():

            df_name = normalize_name(name)

            if df_name not in df.columns:
                self.logger.info(f"{name} ({df_name}) not in data set.")
                continue

            # use pop total from same year / source
            dfx_total = df_total[df_total['HEALTH WORKERS'].isin([
                'TOTAL POPULATION',
            ])]
            totals = {}
            for _, row in dfx_total.iterrows():
                totals[int(row['YEAR'])] = int(row[df_name])


            dfx = df[df['HEALTH WORKERS'].isin([
                'MEDICAL LABORATORY TECHNOLOGIST',
            ])]

            for _, row in dfx.iterrows():

                if totals[int(row['YEAR'])] == 0:
                    self.logger.info(f"Total pop for {name} ({df_name}) in {row['YEAR']} is 0.")
                    continue

                rows.append({
                    'year': int(row['YEAR']),
                    'shape_id': shape_id,
                    f"{self.parameter_id}": row[df_name] / totals[int(row['YEAR'])] * 10000
                })

        self.df = pd.DataFrame(rows)
        self.save()
