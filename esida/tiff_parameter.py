import os
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import rasterio.mask
import fiona

from dbconf import get_engine
from esida.parameter import BaseParameter

class TiffParameter(BaseParameter):
    """ Extends BaseParameter class for GeoTiff consumption. """

    def __init__(self):
        super().__init__()
        self.manual_nodata = None

    def consume(self, file, band, shape):
        raise NotImplementedError

    def load(self, shapes=None, save_output=False):
        param_dir = self.get_data_path()
        files = sorted([s for s in os.listdir(param_dir) if s.rpartition('.')[2] in ('tiff','tif')])

        if shapes is None:
            shapes = self._get_shapes_from_db()

        file_count = len(files)
        i = 1

        for file in files:
            self.logger.info("loading file (%s of %s): %s", i, file_count, file)
            i += 1

            with rasterio.open(param_dir / file) as src:
                nodata = src.nodata
                self.logger.debug("No data is: %s", nodata)

                # GeoTiff has NO NoData meta data set, try to use custom
                # set NoData value
                if nodata is None:
                    nodata = self.manual_nodata

                # make sure manual_nodata is set
                if nodata is None:
                    raise ValueError(f"No NoData value for GeoTiff {file}")

                for shape in shapes:
                    self.logger.debug("loading shape: %s", shape['name'])

                    if "geometry" in shape:
                        mask = [shape['geometry']]
                    elif "file" in shape:
                        with fiona.open(shape['file'], "r") as shapefile:
                            mask = [feature["geometry"] for feature in shapefile]
                    else:
                        raise ValueError("No geometry found for given shape.")

                    out_image, out_transform = rasterio.mask.mask(src, mask, crop=True, nodata=nodata)
                    out_meta = src.meta

                    if save_output:
                        out_meta.update({"driver": "GTiff",
                                        "height": out_image.shape[1],
                                        "width": out_image.shape[2],
                                        "transform": out_transform})

                        shape_name = os.path.splitext(os.path.basename(shape['name']))[0]

                        out_file = self.get_output_path(shape_name) / file
                        Path(os.path.dirname(out_file)).mkdir(parents=True, exist_ok=True)
                        with rasterio.open(out_file, "w", **out_meta) as dest:
                            dest.write(out_image)

                    band1 = out_image[0]

                    # To mask NoData cells we use np.nan so we can use np.nan*-methods.
                    # But np.nan is only available inside float arrays, not with
                    # int arrays!
                    # So in case we have a int array GeoTiff, we need to check
                    # and convert it to a float array.
                    if np.issubdtype(band1.dtype, np.integer):
                        band1 = band1.astype(np.float32)

                    band1[band1==nodata] = np.nan

                    self.consume(file, band1, shape)

        self.save()
