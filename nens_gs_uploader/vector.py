# -*- coding: utf-8 -*-
"""#
Created on Fri Apr 26 16:39:50 2019

@author: chris.kerklaan

Utils used for gis programming
"""

# Third party imports
import os
import osr
import ogr
import gdal
from tqdm import tqdm


# Local imports
from nens_gs_uploader.postgis import connect2pg_database
from nens_gs_uploader.upload_ready import correct

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
        
def vector_clip(in_layer, clip_geom):
    out_datasource = DRIVER_OGR_MEM.CreateDataSource("temp")
    out_layer = out_datasource.CreateLayer("temp", 
                                           in_layer.GetSpatialRef(),
                                           in_layer.GetGeomType())

    in_layer_defn = in_layer.GetLayerDefn()
    
    in_layer.SetSpatialFilter(clip_geom)
     
    # Copy fields from memory layer to output dataset
    for i in range(in_layer_defn.GetFieldCount()):
        out_layer.CreateField(in_layer_defn.GetFieldDefn(i))

    print('start masking')
    for out_feat in tqdm(in_layer):
        out_geom = out_feat.geometry()
        
        # no self intersection
        out_geom = out_geom.Buffer(0)

        if out_geom.Intersects(clip_geom.Boundary()):
            intersect = out_geom.Intersection(clip_geom)
            intersect_type = intersect.GetGeometryType() 
            
            if intersect_type > 3 or intersect_type < 0: # multiparts
                for geom_part in intersect:
                    if not geom_part.IsValid():
                        print("skipping invalid part")
                        continue

                    out_feat.SetGeometry(geom_part)
                    out_layer.CreateFeature(out_feat)
                    
            else:
                out_feat.SetGeometry(intersect)
                out_layer.CreateFeature(out_feat)
                
        elif out_geom.Within(clip_geom):
            out_feat.SetGeometry(out_geom)
            out_layer.CreateFeature(out_feat)
           
        else:
            pass
    in_layer  = None
    out_layer = None
    
    return out_datasource

def vector_to_geom(vector_path):
    vector_ds = ogr.Open(vector_path)
    vector_layer = vector_ds[0]
    
    # reproject
    out_datasource, layer_name = correct(vector_layer, 'Dummy')
    out_layer = out_datasource[0]

    # dissolve
    if out_layer.GetFeatureCount() != 1:
        union_poly = ogr.Geometry(ogr.wkbPolygon)
        for feat in out_layer:
            out_geom = feat.geometry()
            union_poly = union_poly.Union(out_geom)
            
        # remove self intersections
        union_poly = union_poly.Buffer(0)
        
    else:
        out_feat =  out_layer[0]
        union_poly = out_feat.geometry()
    
    

    return union_poly


if __name__ == '__main__':
    sys.path.append('C:/Users/chris.kerklaan/tools')
    flood_dir = 'C:/Users/chris.kerklaan/Documents/Projecten/flooding/upload'
    os.chdir('C:/Users/chris.kerklaan/Documents/Projecten/flooding/upload_test')
    _dir = [i for i in  os.listdir(flood_dir) if 'vg' in i and ".shp" in i]
    vector_geom = vector_to_geom('C:/Users/chris.kerklaan/Documents/Projecten/flooding/nl_mask2.shp')
        
    for i in _dir:
        input_ds = ogr.Open(os.path.join(flood_dir,i))
        input_layer = input_ds[0]
        correct_ds, layer_name = correct(input_layer, 'Dummy')
        correct_layer = correct_ds[0]
        output_ds = vector_clip(correct_layer, vector_geom)
        
        out_source = DRIVER_OGR_SHP.CreateDataSource(i)
        out_layer = out_source.CopyLayer(output_ds[0], "layer", ["OVERWRITE=YES"])
        out_source = None
