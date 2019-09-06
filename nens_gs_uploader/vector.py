# -*- coding: utf-8 -*-
"""#
Created on Fri Apr 26 16:39:50 2019

@author: chris.kerklaan

Utils used for gis programming
"""

# Third party imports
import osr
import ogr
import gdal

# Local imports
from postgis import connect2pg_database

# Global DRIVERS
DRIVER_GDAL_MEM = gdal.GetDriverByName("MEM")
DRIVER_OGR_SHP = ogr.GetDriverByName("ESRI Shapefile")
DRIVER_OGR_MEM = ogr.GetDriverByName("Memory")

# Shapes
POLYGON = "POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"
POINT = "POINT ({x1} {y1})"


class wrap_shape(object):
    """wrapper of shapefile"""

    def __init__(self, datasource, layername=None, epsg=28992):
        if type(datasource) is str:
            self.datasource = ogr.Open(datasource, 1)
        elif type(datasource) is dict:
            self.datasource = ogr.Open(connect2pg_database(datasource), 1)
        else:
            self.datasource = datasource

        if layername is None:
            self.layer = self.datasource[0]
            self.layer_defn = self.layer.GetLayerDefn()
        else:
            self.layer = self.datasource.GetLayer(layername)
            self.layer_defn = self.layer.GetLayerDefn()

        self.layers = [layer.GetName() for layer in self.datasource]
        self.sr = self.layer.GetSpatialRef()
        # self.geom = self.layer[0].GetGeometryRef()
        # self.geom_type = self.geom.GetGeometryType()
        self.layer.ResetReading()
        self.geom_type = ogr.wkbPolygon

    def get_layer(self, layer_name):
        self.layer = self.datasource.GetLayerByName(layer_name)
        self.layer_defn = self.layer.GetLayerDefn()

    def set_size(self):
        self.size = (
            int((self.xmax - self.xmin) / 0.5),
            int((self.ymax - self.ymin) / 0.5),
        )

    def get_spatial_reference(self, epsg=28992):
        sr = osr.SpatialReference()
        sr.ImportFromEPSG(epsg)
        self.sr = sr

    def set_geotransform(self):
        self.geotransform = (self.xmin, 0.5, 0, self.ymax, 0, -0.5)

    def set_spatial_filter(self, geometry):
        self.layer.SetSpatialFilter(self.geometry)

    def set_attribute_filter(self, string):
        self.layer.SetAttributeFilter(string)

    def get_field_names(self):
        for i in range(self.layer_defn.GetFieldCount()):
            yield self.layer_defn.GetFieldDefn(i).GetName()

    def get_fields(self):
        for field in self.layer:
            yield field

    def get_field_defns(self):
        for i in range(self.layer_defn.GetFieldCount()):
            yield self.layer_defn.GetFieldDefn(i)

    def get_all_field_names(self):
        return [str(field_name) for field_name in self.get_field_names()]

    def create_dummy_layer(self):
        mem_datasource = DRIVER_OGR_MEM.CreateDataSource("mem")
        mem_layer = mem_datasource.CreateLayer("", self.sr, self.geom_type)

        for i in range(self.layer_defn.GetFieldCount()):
            mem_layer.CreateField(self.layer_defn.GetFieldDefn(i))
        return mem_layer

    def memory2input(self):
        self.datasource = self.mem_datasource
        self.layer = self.mem_layer

    def create_outputfile(self, layer_name, path_name):
        self.set_spatial_reference()

        self.out_datasource = DRIVER_OGR_SHP.CreateDataSource(path_name)
        self.out_layer = self.out_datasource.CreateLayer(
            layer_name, self.sr, self.geom_type
        )
        for i in range(self.layer_defn.GetFieldCount()):
            self.out_layer.CreateField(self.layer_defn.GetFieldDefn(i))

    def copy_datasource(self, out_layer):
        """ copy layer from in_file """
        self.out_datasource = DRIVER_OGR_SHP.CopyDataSource(
            self.datasource, out_layer
        )
        self.out_layer = self.out_datasource[0]
        self.layer.ResetReading()

    def create_field(self, attributes):
        """ Create a new field within output shape. """
        for key, value in attributes.items():
            self.out_layer.CreateField(ogr.FieldDefn(key, value))

    def set_field(self, feature_number, field_name, field_value):
        """ Set a field value based on a feature number. """
        feature = self.out_layer.GetFeature(feature_number)
        feature.SetField(field_name, field_value)
        self.out_layer.SetFeature(feature)
        feature = None

    def append_feature(self, geometry, attributes):
        """ Append geometry and attributes as new feature. """
        feature = ogr.Feature(self.layer_defn)
        feature.SetGeometry(geometry)
        for key, value in attributes.items():
            feature[str(key)] = value
        self.layer.CreateFeature(feature)

    def query(self, geometry):
        """ Return generator of features with geometry as spatial filter. """
        self.layer.SetSpatialFilter(geometry)
        for feature in self.layer:
            yield feature
        self.layer.SetSpatialFilter(None)

    def write_output_file(self):
        self.out_layer = None
        self.out_datasource = None

    def lower_all_field_names(self):
        for field_defn in self.get_field_defns():
            field_defn.SetName(field_defn.GetName().lower())

    def get_geom_transform(self, out_epsg=28992):

        out_spatial_ref = osr.SpatialReference()
        out_spatial_ref.ImportFromEPSG(out_epsg)

        coordTrans = osr.CoordinateTransformation(self.sr, out_spatial_ref)

        return coordTrans

    def write_geometries(self, layer_name, path_name):
        try:
            self.set_spatial_reference()

            data_source = DRIVER_OGR_SHP.CreateDataSource(path_name)
            out_layer = data_source.CreateLayer(
                layer_name, self.sr, self.geom_type
            )

            for i in range(self.layer_defn.GetFieldCount()):
                out_layer.CreateField(self.layer_defn.GetFieldDefn(i))
            for feat in self.layer:
                out_layer.CreateFeature(feat)

        finally:
            out_layer = data_source = None

    def multipoly2poly(self, in_lyr, out_lyr):
        for in_feat in in_lyr:
            geom = in_feat.GetGeometryRef()
            if geom.GetGeometryName() == "MULTIPOLYGON":
                for geom_part in geom:
                    self.addPolygon(geom_part.ExportToWkb(), out_lyr)
            else:
                self.addPolygon(geom.ExportToWkb(), out_lyr)

    def addPolygon(self, simplePolygon, out_lyr):
        featureDefn = out_lyr.GetLayerDefn()
        polygon = ogr.CreateGeometryFromWkb(simplePolygon)
        out_feat = ogr.Feature(featureDefn)
        out_feat.SetGeometry(polygon)
        out_lyr.CreateFeature(out_feat)
