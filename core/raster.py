# -*- coding: utf-8 -*-
"""
Created on Wed Jan 29 18:20:00 2020

@author: chris.kerklaan

raster wrapper used for gis programming
"""
import osr
import ogr
import gdal

from tqdm import tqdm

# globals
DRIVER_OGR_SHP = ogr.GetDriverByName("ESRI Shapefile")
DRIVER_GDAL_GTIFF = gdal.GetDriverByName("GTiff")

type_mapping = {
    gdal.GDT_Byte: ogr.OFTInteger,
    gdal.GDT_UInt16: ogr.OFTInteger,
    gdal.GDT_Int16: ogr.OFTInteger,
    gdal.GDT_UInt32: ogr.OFTInteger,
    gdal.GDT_Int32: ogr.OFTInteger,
    gdal.GDT_Float32: ogr.OFTReal,
    gdal.GDT_Float64: ogr.OFTReal,
    gdal.GDT_CInt16: ogr.OFTInteger,
    gdal.GDT_CInt32: ogr.OFTInteger,
    gdal.GDT_CFloat32: ogr.OFTReal,
    gdal.GDT_CFloat64: ogr.OFTReal,
}
_mem_num = 0


class wrap_raster(object):
    def __init__(self, path, band_num=1):
        if type(path) is str:
            self.ds = gdal.Open(path)
        else:
            self.ds = path

        self.band = self.ds.GetRasterBand(band_num)
        self.nodata_value = self.band.GetNoDataValue()
        self.array = self.band.ReadAsArray()
        self.rows, self.columns = self.array.shape
        self.geotransform = self.ds.GetGeoTransform()

        ### set nodata to -9999
        self.array[self.array == self.nodata_value] = -9999
        self.band.SetNoDataValue(-9999)
        self.nodata_value = -9999

    def reload(self, path, band_num=1):
        if type(path) is str:
            self.ds = gdal.Open(path)
        else:
            self.ds = path
        self.band = self.ds.GetRasterBand(band_num)
        self.nodata_value = self.band.GetNoDataValue()
        self.array = self.band.ReadAsArray()
        self.rows, self.columns = self.array.shape
        self.geotransform = self.ds.GetGeoTransform()
        self.array[self.array == self.nodata_value] = -9999
        self.band.SetNoDataValue(-9999)
        self.nodata_value = -9999

    def clip(self, vector_layer, output_path="/vsimem/clip.tif"):
        self.ds = gdal.Warp(
            output_path, self.ds, cutlineLayer=vector_layer, cropToCutline=True
        )
        self.array = self.ds.ReadAsArray()
        self.geotransform = self.ds.GetGeoTransform()

    def write(self, array, filename, geotransform, epsg=28992, nodata=-9999):
        out = DRIVER_GDAL_GTIFF.Create(
            filename,
            array.shape[1],
            array.shape[0],
            1,
            gdal.GDT_Float32,
            options=["COMPRESS=DEFLATE"],
        )
        out.SetGeoTransform(geotransform)
        srs = osr.SpatialReference()  # establish encoding
        srs.ImportFromEPSG(epsg)
        out.SetProjection(srs.ExportToWkt())  # export coords to file
        out.GetRasterBand(1).WriteArray(array)
        if nodata is not None:
            out.GetRasterBand(1).SetNoDataValue(nodata)
            out.FlushCache()  # write to disk
            out = None

    def polygonize(
        self,
        field_name="dn",
        vector_path="/vsimem/polygonized.shp",
        layer_name="poly",
        verbose=False,
        no_mask=False,
    ):
        global _mem_num
        prj = self.ds.GetProjection()
        vector_path = f"/vsimem/polygonized_{_mem_num}.shp"
        _mem_num = _mem_num + 1
        ds_vector = DRIVER_OGR_SHP.CreateDataSource(vector_path)
        srs = osr.SpatialReference(wkt=prj)
        layer_vector = ds_vector.CreateLayer(layer_name, srs=srs)
        raster_field = ogr.FieldDefn(field_name, type_mapping[self.band.DataType])
        layer_vector.CreateField(raster_field)

        if no_mask:
            no_data_band = None
        else:
            no_data_band = self.band.GetMaskBand()

        if verbose:
            gdal.Polygonize(self.band, no_data_band, layer_vector, 1, [])
        else:
            gdal.Polygonize(
                self.band, no_data_band, layer_vector, 1, [], callback=progress_callback
            )

        return ds_vector, layer_vector

    def resample(self, x_res, y_res):
        self.ds = gdal.Translate(
            "/vsimem/xr.tif",
            self.ds,
            xRes=x_res,
            yRes=y_res,
            resampleAlg=gdal.GRA_NearestNeighbour,
        )
        self.array = self.ds.ReadAsArray()
        self.geotransform = self.ds.GetGeoTransform()
        self.band = self.ds.GetRasterBand(1)
        self.array[self.array > 100000000] = self.nodata_value

    def polygonize_in_tiles(self, n=5):
        self.vector_tiles = polygonize_in_tiles(self.ds, n)

    def polygon_shape(self, threshold=0, verbose=True):
        global _mem_num
        vector_path = f"/vsimem/shape_{_mem_num}.tif"
        _mem_num = _mem_num + 1
        self.array[(self.array > threshold) & (self.array != self.nodata_value)] = 1
        self.array[(self.array <= threshold)] = self.nodata_value

        self.write(self.array, vector_path, self.geotransform)
        self.reload(vector_path)
        ds, layer = self.polygonize(verbose=verbose)
        return ds, layer


def resample(ds, x_res, y_res):
    ds = gdal.Translate(
        "/vsimem/xr.tif",
        ds,
        xRes=x_res,
        yRes=y_res,
        resampleAlg=gdal.GRA_NearestNeighbour,
    )
    array = ds.ReadAsArray()
    return ds, array


def progress_callback(complete, message, unknown):
    print(
        'progress: {}, message: "{}", unknown {}'.format(
            round(complete, 2), message, unknown
        )
    )
    return 1


def get_extent(dataset):

    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    transform = dataset.GetGeoTransform()
    minx = transform[0]
    maxx = transform[0] + cols * transform[1] + rows * transform[2]

    miny = transform[3] + cols * transform[4] + rows * transform[5]
    maxy = transform[3]

    return {
        "minX": str(minx),
        "maxX": str(maxx),
        "minY": str(miny),
        "maxY": str(maxy),
        "cols": str(cols),
        "rows": str(rows),
    }


def create_tiles(minx, miny, maxx, maxy, n):
    width = maxx - minx
    height = maxy - miny

    matrix = []

    for j in range(n, 0, -1):
        for i in range(0, n):

            ulx = minx + (width / n) * i  # 10/5 * 1
            uly = miny + (height / n) * j  # 10/5 * 1

            lrx = minx + (width / n) * (i + 1)
            lry = miny + (height / n) * (j - 1)
            matrix.append([[ulx, uly], [lrx, lry]])

    return matrix


def split(dataset, n):
    """ returns in memory rasters"""
    global _mem_num
    band = dataset.GetRasterBand(1)
    transform = dataset.GetGeoTransform()

    extent = get_extent(dataset)

    cols = int(extent["cols"])
    rows = int(extent["rows"])

    minx = float(extent["minX"])
    maxx = float(extent["maxX"])
    miny = float(extent["minY"])
    maxy = float(extent["maxY"])

    width = maxx - minx
    height = maxy - miny

    tiles = create_tiles(minx, miny, maxx, maxy, n)
    transform = dataset.GetGeoTransform()
    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = -transform[5]

    chunks = []
    for tile in tqdm(tiles):
        _mem_num = _mem_num + 1
        name = "/vsimem/raster_{}.tif".format(_mem_num)

        minx = tile[0][0]
        maxx = tile[1][0]
        miny = tile[1][1]
        maxy = tile[0][1]

        p1 = (minx, maxy)
        p2 = (maxx, miny)

        i1 = int((p1[0] - xOrigin) / pixelWidth)
        j1 = int((yOrigin - p1[1]) / pixelHeight)
        i2 = int((p2[0] - xOrigin) / pixelWidth)
        j2 = int((yOrigin - p2[1]) / pixelHeight)

        new_cols = i2 - i1
        new_rows = j2 - j1

        data = band.ReadAsArray(i1, j1, new_cols, new_rows)

        # print data

        new_x = xOrigin + i1 * pixelWidth
        new_y = yOrigin - j1 * pixelHeight

        new_transform = (
            new_x,
            transform[1],
            transform[2],
            new_y,
            transform[4],
            transform[5],
        )
        dst_ds = DRIVER_GDAL_GTIFF.Create(name, new_cols, new_rows, 1, gdal.GDT_Float32)

        dst_ds.GetRasterBand(1).WriteArray(data)

        tif_metadata = {
            "minX": str(minx),
            "maxX": str(maxx),
            "minY": str(miny),
            "maxY": str(maxy),
        }
        dst_ds.SetMetadata(tif_metadata)

        # setting extension of output raster
        # top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution
        dst_ds.SetGeoTransform(new_transform)

        wkt = dataset.GetProjection()

        # setting spatial reference of output raster
        srs = osr.SpatialReference()
        srs.ImportFromWkt(wkt)
        dst_ds.SetProjection(srs.ExportToWkt())

        # Close output raster dataset
        dst_ds = None

        chunks.append(name)

    return chunks


def polygonize_in_tiles(raster_ds, n=5):

    chunks = split(raster_ds, n)

    vectors = []
    for tile in tqdm(chunks):
        raster = wrap_raster(tile)

        vector_ds, vector_layer = raster.polygonize(field_name="koel", verbose=True)
        vectors.append(vector_ds)
    return vectors


if __name__ == "__main__":
    os.chdir(
        "C://Users/chris.kerklaan/Documents/Projecten/lochem/looptijd_tot_koelte/input"
    )
    raster = wrap_raster("pet_boolean_small.tif")
