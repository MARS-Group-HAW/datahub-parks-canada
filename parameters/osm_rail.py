import datetime as dt

import pandas as pd
import osmnx as ox
import geopandas
import fiona

from esida.parameter import BaseParameter
from dbconf import get_engine

class osm_rail(BaseParameter):

    def __init__(self):
        super().__init__()

        # table name for the cleaned records
        # can not be osm_airports. this name is used for the parameter!
        # but we want to store queried POIs as well
        self.table_name = f'data_{self.parameter_id}'

    def extract(self):
        ox.settings.log_console=True
        ox.settings.use_cache=True
        ox.settings.cache_folder=self.get_data_path()
        ox.settings.timeout = 1800

        # get convex hull for all loaded shapes, and query all airports for the
        # resulting convex hull polygon
        shp = self._get_convex_hull_from_db()

        # In OSM regular passenger/freight trains are tagged with railway=rail.
        # Wie use geometries_from_polygon() instead of graph_from_polygon(),
        # b/c due to the nature of OSM there might be gaps in the lines/wrongly
        # tagged line segments, and the graph method would remove parts that
        # prevent it from building a graph. With the geometries function we get
        # all available segments.
        # Since we only need a "is there some railway in the area" type of query
        # we actually don't need a graph.

        #gdf = ox.geometries_from_polygon(
        #    shp,
        #    {
        #        'railway': "rail"
        #    }
        #)

        G = ox.graph_from_polygon(
            shp,
            simplify=True,
            retain_all=True,
            custom_filter='["railway"="rail"]'
        )

        gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
        gdf_nodes = ox.io._stringify_nonnumeric_cols(gdf_nodes)
        gdf_edges = ox.io._stringify_nonnumeric_cols(gdf_edges)

        # flatten MultiIndex created by OSMnx
        gdf = gdf_edges.reset_index(drop=True)

        # drop all columns where each row is NULL
        gdf = gdf.dropna(axis=1,how='all')

        gdf.to_postgis(self.table_name, con=get_engine(), if_exists='replace')

    def load(self, shapes=None, save_output=False):

        if shapes is None:
            shapes = self._get_shapes_from_db()

        # load imported data
        df = geopandas.read_postgis(f"SELECT * FROM {self.table_name}",
                            geom_col='geometry', con=get_engine())

        dfs = []

        for shape in shapes:
            self.logger.debug("loading shape: %s", shape['name'])

            if "geometry" in shape:
                mask = [shape['geometry']]
            elif "file" in shape:
                with fiona.open(shape['file'], "r") as shapefile:
                    mask = [feature["geometry"] for feature in shapefile]
            else:
                raise ValueError("No geometry found for given shape.")

            # clip to only POIs within area of interest
            dfx = df[df['geometry'].intersects(mask[0])]

            # group / count matching facilities per year
            has_rail = 0
            if len(dfx) > 0:
                has_rail = 3.2 # https://www.theglobaleconomy.com/rankings/railroad_quality/

            dfs.append({
                'shape_id': shape['id'],
                'year': dt.datetime.now().year,
                self.parameter_id: has_rail
            })

        dfsx = pd.DataFrame(dfs)
        dfsx.to_sql(self.parameter_id, con=get_engine(), if_exists='replace')
