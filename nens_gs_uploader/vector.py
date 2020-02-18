"""#
Created on Fri Apr 26 16:39:50 2019

@author: chris.kerklaan

Vector wrapper used for GIS programming


"""
# System imports
import os
import sys

# Relevant paths
BASE = "C:/Users/chris.kerklaan/tools"
if BASE not in sys.path:
    sys.path.append(BASE)

# Third party imports
import osr
import ogr
import gdal
from tqdm import tqdm

# Local imports
from nens_gs_uploader.postgis import connect2pg_database
from nens_gs_uploader.project import log_time

# Global DRIVERS
DRIVER_GDAL_MEM = gdal.GetDriverByName("MEM")
DRIVER_OGR_SHP = ogr.GetDriverByName("ESRI Shapefile")
DRIVER_OGR_GPKG = ogr.GetDriverByName("GPKG")
DRIVER_OGR_MEM = ogr.GetDriverByName("Memory")
_mem_num = 0

# Shapes
POLYGON = "POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"
POINT = "POINT ({x1} {y1})"

# Exceptions
ogr.UseExceptions()


class wrap_shape(object):
    """wrapper of shapefile"""

    def __init__(self, ds, layername=None, epsg=28992):
        if type(ds) is str:
            self.ds = ogr.Open(ds, 1)
        elif type(ds) is dict:
            self.ds = ogr.Open(connect2pg_database(ds), 1)
        else:
            self.ds = ds

        if layername is None:
            self.layer = self.ds[0]
            self.layer_defn = self.layer.GetLayerDefn()
        else:
            self.layer = self.ds.GetLayer(layername)
            self.layer_defn = self.layer.GetLayerDefn()

        self.layers = [layer.GetName() for layer in self.ds]
        self.sr = self.layer.GetSpatialRef()
        self.layer.ResetReading()
        self.geom_type = self.layer.GetGeomType()

    def get_layer(self, layer_name):
        self.layer = self.ds.GetLayerByName(layer_name)
        self.layer_defn = self.layer.GetLayerDefn()
        return self.layer

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
        self.ds = self.mem_datasource
        self.layer = self.mem_layer

    def create_outputfile(self, layer_name, path_name, epsg=28992):
        self.get_spatial_reference(epsg=epsg)

        self.out_datasource = DRIVER_OGR_SHP.CreateDataSource(path_name)
        self.out_layer = self.out_datasource.CreateLayer(
            layer_name, self.sr, self.geom_type
        )
        for i in range(self.layer_defn.GetFieldCount()):
            self.out_layer.CreateField(self.layer_defn.GetFieldDefn(i))

    def copy_datasource(self, out_layer):
        """ copy layer from in_file """
        self.out_datasource = DRIVER_OGR_SHP.CopyDataSource(self.ds, out_layer)
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

    def close_connection(self):
        self.layer = None
        self.ds = None

    def write(self, ogr_layer, path_name, layer_name="vect", epsg=28992):

        self.get_spatial_reference(epsg=epsg)

        if os.path.splitext(path_name)[1] == ".gpkg":
            data_source = DRIVER_OGR_GPKG.CreateDataSource(path_name)
        else:
            data_source = DRIVER_OGR_SHP.CreateDataSource(path_name)

        out_layer = data_source.CreateLayer(layer_name, self.sr, self.geom_type)

        for i in range(self.layer_defn.GetFieldCount()):
            out_layer.CreateField(self.layer_defn.GetFieldDefn(i))

        ogr_layer.ResetReading()
        for feat in ogr_layer:
            out_layer.CreateFeature(feat)

        out_layer = None
        data_source = None

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

    def change_source(self, in_ds, in_layer):
        self.ds = None
        self.layer = None
        self.ds = in_ds
        self.layer = in_layer

    def correct(self, layer, name="", epsg=28992):
        self.ds_correct, self.layer_name = correct(layer, layer_name=name, epsg=epsg)
        self.layer_correct = self.ds_correct[0]
        self.change_source(self.ds_correct, self.layer_correct)

    def clip(self, layer, clip_geom):
        self.ds_clip = clip(layer, clip_geom)
        self.layer_clip = self.ds_clip[0]
        self.change_source(self.ds_clip, self.layer_clip)

    def dissolve(self, layer):
        self.ds_dissolve = dissolve(layer)
        self.layer_dissolve = self.ds_dissolve[0]
        self.change_source(self.ds_dissolve, self.layer_dissolve)

    def difference(self, vector_layer, difference_layer):
        self.ds_difference = difference(vector_layer, difference_layer)
        self.layer_difference = self.ds_difference[0]
        self.change_source(self.ds_difference, self.layer_difference)

    def multi2single(self, vector_layer):
        self.ds_single = multiparts_to_singleparts(vector_layer)
        self.layer_single = self.ds_single[0]
        self.change_source(self.ds_single, self.layer_single)


def create_geom_transform(in_spatial_ref, out_epsg):
    """Return coordinate transformation based on two reference systems"""
    out_spatial_ref = osr.SpatialReference()
    out_spatial_ref.ImportFromEPSG(out_epsg)
    coordTrans = osr.CoordinateTransformation(in_spatial_ref, out_spatial_ref)
    return coordTrans, out_spatial_ref


def create_mem_ds():
    global _mem_num
    mem_datasource = DRIVER_OGR_SHP.CreateDataSource("/vsimem/mem{}".format(_mem_num))
    _mem_num = _mem_num + 1
    return mem_datasource


def geom_transform(in_spatial_ref, out_epsg):
    out_spatial_ref = osr.SpatialReference()
    out_spatial_ref.ImportFromEPSG(out_epsg)
    coordTrans = osr.CoordinateTransformation(in_spatial_ref, out_spatial_ref)
    return coordTrans


def copymem(vector_layer, layer_name="mem", geom_type=ogr.wkbPolygon, spatial_ref=None):
    """ makes a copy of the vector_layer and returns a memory ds and layer"""
    if spatial_ref is None:
        spatial_ref = vector_layer.GetSpatialRef()

    out_datasource = create_mem_ds()
    out_layer = out_datasource.CreateLayer(layer_name, spatial_ref, geom_type)

    vector_layer_defn = vector_layer.GetLayerDefn()
    for i in range(vector_layer_defn.GetFieldCount()):
        out_layer.CreateField(vector_layer_defn.GetFieldDefn(i))

    return out_datasource, out_layer


def multipoly2poly(in_layer, out_layer):

    lost_features = []
    layer_defn = in_layer.GetLayerDefn()
    field_names = []

    for n in range(layer_defn.GetFieldCount()):
        field_names.append(layer_defn.GetFieldDefn(n).name)

    for count, in_feat in enumerate(in_layer):
        content = in_feat.items()
        # for field_name in field_names:
        #     content[field_name] = in_feat.GetField(field_name)

        geom = in_feat.GetGeometryRef()
        if geom == None:
            print("warning", "FID {} has no geometry.".format(count))
            lost_features.append(in_feat.GetFID())
            continue

        geom_name = geom.GetGeometryName()

        if "multi" in geom_name.lower():
            for geom_part in geom:
                addPolygon(geom_part.ExportToWkb(), content, out_layer)
        else:
            addPolygon(geom.ExportToWkb(), content, out_layer)

    return lost_features


def addPolygon(simple_polygon, content, out_lyr):
    featureDefn = out_lyr.GetLayerDefn()

    polygon = ogr.CreateGeometryFromWkb(simple_polygon)
    out_feat = ogr.Feature(featureDefn)
    out_feat.SetGeometry(polygon)

    for key, value in content.items():
        try:
            out_feat.SetField(key, value)
        except Exception as e:
            print(e)

    out_lyr.CreateFeature(out_feat)


def append_feature(layer, layer_defn, geometry, attributes):
    """ Append geometry and attributes as new feature. """
    feature = ogr.Feature(layer_defn)
    feature.SetGeometry(geometry)
    for key, value in attributes.items():
        feature[str(key)] = value
    layer.CreateFeature(feature)
    return layer


def multiparts_to_singleparts(vector_layer):
    out_datasource, out_layer = copymem(vector_layer, geom_type=ogr.wkbPolygon)
    multipoly2poly(vector_layer, out_layer)
    out_layer = None
    return out_datasource


def fix_geometry(geometry):
    """
    Fixes a geometry:
        1. pointcount for  linestrings 
        2. self intersections for polygons
        3. slivers

    Parameters
    ----------
    geometry : ogr geometry

    Returns
    -------
    geometry: ogr geometry
    geometry validity: bool

    """
    if geometry is None:
        return None, False

    geom_name = geometry.GetGeometryName()

    # check pointcount if linestring
    if "LINESTRING" in geom_name:
        if geometry.GetPointCount() == 1:
            log_time("error", "Geometry point count of linestring = 1")
            return geometry, False
        else:
            pass

    # solve self intersections
    if "POLYGON" in geom_name:
        try:
            geometry = geometry.Buffer(0)
        except Exception as e:
            # RuntimeError: IllegalArgumentException: Points of LinearRing do not form a closed linestring
            log_time("error", e)
            return geometry, False

    # most likely does not do anything
    # check slivers
    # if not geometry.IsValid():
    #     perimeter = geometry.Boundary().Length()
    #     area = geometry.GetArea()
    #     sliver = float(perimeter / area)

    #     if sliver < 1:
    #         wkt = geometry.ExportToWkt()
    #         geometry = ogr.CreateGeometryFromWkt(wkt)

    return geometry, geometry.IsValid()


def correct(in_layer, layer_name="", epsg=3857):
    """
    This function standardizes a vector layer:
        1. Multipart to singleparts
        2. 3D polygon to 2D polygon
        3. Reprojection
        4. Fix geometry for self intersections    

    Parameters
    ----------
    in_layer : ogr layer
    layer_name : string, optional
        The default is ''.
    epsg : int, optional
        The default is 3857.

    Raises
    ------
    ValueError
        For a z-type geometry

    Returns
    -------
    out_datasource : ogr datasource

    """

    try:
        # retrieving lost features
        lost_features = []
        in_feature_count = in_layer.GetFeatureCount()

        # reset reading
        in_layer.ResetReading()

        layer_name = layer_name.lower()
        log_time("info", "check - Name length")
        if len(layer_name) + 10 > 64:
            log_time("error", "laagnaam te lang, 50 characters max.")
            log_time("info", "formatting naar 50 met deze naam: %s" % layer_name[:50])
            layer_name = layer_name[:50]

        # Create output dataset and force dataset to multiparts
        geom_type = in_layer.GetGeomType()
        geom_name = ogr.GeometryTypeToName(geom_type)
        if "polygon" in geom_name.lower():
            output_geom_type = 3  # polygon
        elif "line" in geom_name.lower():
            output_geom_type = 2  # linestring
        elif "point" in geom_name.lower():
            output_geom_type = 1  # point
        else:
            log_time(
                "Error", "Geometry could not be translated to singlepart %s" % geom_name
            )
            raise TypeError()

        mem_datasource, mem_layer = copymem(in_layer, geom_type=output_geom_type)

        log_time("info", "check - Multipart to singlepart")
        lost_feat = multipoly2poly(in_layer, mem_layer)
        lost_features = lost_features + lost_feat

        if mem_layer.GetFeatureCount() == 0:
            log_time("error", "Multipart to singlepart failed")
            return 1

        in_spatial_ref = in_layer.GetSpatialRef()
        # print(in_spatial_ref, int(epsg))
        reproject, out_spatial_ref = create_geom_transform(in_spatial_ref, int(epsg))

        flatten = False
        if "3D" in geom_name:
            log_time("warning", "geom type: " + geom_name)
            log_time("info", "Flattening to 2D")
            flatten = True

        elif geom_type < 0:
            log_time("error", "geometry invalid, most likely has a z-type")
            raise ValueError(
                "geometry invalid, most likely has a z-type", "geom type: ", geom_name
            )

        out_datasource, out_layer = copymem(
            in_layer, geom_type=output_geom_type, spatial_ref=out_spatial_ref
        )

        print("info", "check - Reproject layer to {}".format(str(epsg)))
        for out_feat in tqdm(mem_layer):
            out_geom = out_feat.GetGeometryRef()

            try:
                out_geom, valid = fix_geometry(out_geom)
            except Exception as e:
                print(e)
                print(out_feat.GetFID())
            if not valid:
                log_time("warning", "geometry invalid even with buffer, skipping")
                lost_features.append(out_feat.GetFID())
                continue

            # Force and transform geometry
            out_geom = ogr.ForceTo(out_geom, output_geom_type)
            out_geom.Transform(reproject)

            # flattening to 2d
            if flatten:
                out_geom.FlattenTo2D()

            # Set geometry and create feature
            out_feat.SetGeometry(out_geom)
            out_layer.CreateFeature(out_feat)

        print("info", "check  - delete ogc_fid if exists")
        out_layer_defn = out_layer.GetLayerDefn()
        for n in range(out_layer_defn.GetFieldCount()):
            field = out_layer_defn.GetFieldDefn(n)
            if field.name == "ogc_fid":
                out_layer.DeleteField(n)
                break

        print("info", "check  - Features count")
        out_feature_count = out_layer.GetFeatureCount()

        if len(lost_features) > 0:
            log_time(
                "warning",
                "Lost {} features during corrections".format(len(lost_features)),
            )
            log_time("warning", "FIDS: {}".format(lost_features))

        elif in_feature_count > out_feature_count:
            log_time("warning", "In feature count greater than out feature count")

        else:
            print("info", "check  - Features count {}".format(out_feature_count))

    except Exception as e:
        print(e)

    finally:
        mem_layer = None
        mem_datasource = None
        out_layer = None

        print("Finished vector corrections")
    return out_datasource, layer_name


def dissolve(vector_layer):
    """
    Dissolved the vector layer into a single multipolygon feature.

    Parameters
    ----------
    vector_layer : ogr vector

    Returns
    -------
    out_datasource : ogr datasource

    """
    out_datasource, out_layer = copymem(
        vector_layer, geom_type=vector_layer.GetGeomType()
    )
    out_layer_defn = out_layer.GetLayerDefn()
    multi = ogr.Geometry(ogr.wkbMultiPolygon)
    vector_layer.ResetReading()
    for feature in tqdm(vector_layer):
        if feature.geometry():
            feature.geometry().CloseRings()  # this copies the first point to the end
            wkt = feature.geometry().ExportToWkt()
            multi.AddGeometryDirectly(ogr.CreateGeometryFromWkt(wkt))
    union = multi.UnionCascaded()

    # if multipoly is False:
    #     for geom in union:
    #         poly = ogr.CreateGeometryFromWkb(geom.ExportToWkb())
    #         feat = ogr.Feature(out_layer_defn)
    #         feature.SetGeometry(poly)
    #         out_layer.CreateFeature(feat)
    # else:
    out_feat = ogr.Feature(out_layer_defn)
    out_feat.SetGeometry(union)
    out_layer.CreateFeature(out_feat)

    out_layer = None
    return out_datasource


def difference(vector_layer, difference_layer):
    """
    This function takes a difference between vector layer and difference layer.
    - Takes into account multiparts and single parts.
    - It also leaves geometries which are not valid. 

    Parameters
    ----------
    vector_layer : ogr layer  - singleparts
        input vector.
    difference_layer : ogr layer
        difference layer.

    Returns
    -------
    out_datasource : ogr datasource - multiparts
    

    """
    vector_layer_geom_type = vector_layer.GetGeomType()
    if vector_layer_geom_type == 1:
        geometry_types = [1, 4]
    elif vector_layer_geom_type == 2:
        geometry_types = [2, 5]
    elif vector_layer_geom_type == 3:
        geometry_types = [3, 6]
    else:
        pass

    out_datasource, out_layer = copymem(vector_layer, geom_type=vector_layer_geom_type)
    vector_layer_defn = vector_layer.GetLayerDefn()

    print("starting to make a difference_layer")

    vector_layer.ResetReading()
    for vector_feat in tqdm(vector_layer):
        vector_geom = vector_feat.GetGeometryRef()
        vector_geom, valid = fix_geometry(vector_geom)

        if not valid:
            print("Input geometry not valid, skipping")
            continue

        difference_layer.ResetReading()
        difference_layer.SetSpatialFilter(vector_geom)

        for fid, difference_feat in enumerate(difference_layer):
            difference_geom = difference_feat.GetGeometryRef()
            difference_geom, valid = fix_geometry(difference_geom)

            if not valid:
                print("Difference layer geometry not valid, skipping")
                continue

            if difference_geom.Intersects(vector_geom):
                difference = vector_geom.Difference(difference_geom)

                diff_part_type = difference.GetGeometryType()
                if diff_part_type not in geometry_types:

                    # Check if geometry collection
                    if diff_part_type == ogr.wkbGeometryCollection:
                        for geom_part in difference:
                            if geom_part.GetGeometryType() == vector_layer_geom_type:
                                vector_geom, valid = fix_geometry(geom_part)

                    else:
                        name = ogr.GeometryTypeToName(diff_part_type)
                        print("Found foreign geometry:", name)
                        continue

                else:
                    vector_geom, valid = fix_geometry(difference)

                # # if diff_part_type > 3 or diff_part_type < 0: # multiparts
                # #     difference = ogr.ForceTo(difference,
                # #                                  vector_layer_geom_type)
                # #     diff_part_type = difference.GetGeometryType()

                # if diff_part_type != vector_layer_geom_type:
                #     name = ogr.GeometryTypeToName(diff_part_type)
                #     print('Found foreign type:', name )
                #     """vector geom stays vector geom"""
                # else:
                #     vector_geom = difference

            else:
                pass

        out_layer = append_feature(
            out_layer, vector_layer_defn, vector_geom, vector_feat.items()
        )

    out_layer = None
    return out_datasource


def clip(in_layer, clip_geom):
    """
    Clips in_layer geometries and clip_geom.
    - Multipart geometries are set as single part
    - Invalid geometries are first fixed, still not valid, then skip
    - Foreign geomtries (e.g., points) which are a result of a clip,
    are also skipped.
    - 

    Parameters
    ----------
    in_layer : ogr layer
    clip_geom : ogr geometry

    Returns
    -------
    out_datasource : ogr datasource

    """

    in_layer_geom_type = in_layer.GetGeomType()
    in_layer.ResetReading()
    in_layer.SetSpatialFilter(clip_geom)

    out_datasource, out_layer = copymem(in_layer, geom_type=in_layer_geom_type)

    print("starting clip")
    for out_feat in tqdm(in_layer):
        out_geom = out_feat.GetGeometryRef()
        try:
            if out_geom.Intersects(clip_geom.Boundary()):
                intersect = out_geom.Intersection(clip_geom)
                intersect_type = intersect.GetGeometryType()

                if not intersect.IsValid():
                    intersect, valid = fix_geometry(intersect)
                    if not valid:
                        print("skipping invalid intersect")
                        continue

                if intersect_type > 3 or intersect_type < 0:  # multiparts
                    for geom_part in intersect:
                        if not geom_part.IsValid():
                            geom_part, valid = fix_geometry(geom_part)
                            if not valid:
                                print("skipping invalid part")
                                continue

                        geom_part_type = geom_part.GetGeometryType()
                        if geom_part_type != in_layer_geom_type:
                            name = ogr.GeometryTypeToName(geom_part_type)
                            print("Found foreign type:", name)
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

        except Exception as e:
            print(e)

    out_layer = None

    return out_datasource


def vector_to_geom(extent_path, epsg=28992):
    extent_vector = wrap_shape(extent_path)
    extent_vector.correct(extent_vector.layer, epsg=epsg)
    extent_feature = extent_vector.layer_correct[0]
    extent_geom = extent_feature.GetGeometryRef()
    extent_geom = extent_geom.Buffer(0)
    return extent_geom


if __name__ == "__main__":
    extent_path = "C:/Users/chris.kerklaan/Documents/Projecten/flooding/extent/extent_dissolved.shp"
    input_dir = "C:/Users/chris.kerklaan/Documents/Projecten/flooding/fixed/fixed_1"
    output_dir = "C:/Users/chris.kerklaan/Documents/Projecten/flooding/output"

    extent_vector = wrap_shape(extent_path)
    # extent_vector.correct(extent_vector.layer, epsg=28992)
    extent_feature = extent_vector.layer[0]
    extent_geom = extent_feature.GetGeometryRef()
    extent_geom = extent_geom.Buffer(0)

    for vector in os.listdir(input_dir):
        print(vector)
        if vector.split(".")[1] != "shp":
            continue
        vector_path = os.path.join(input_dir, vector)
        vector_out_path = os.path.join(output_dir, vector.split(".")[0] + "_clip.shp")
        if os.path.exists(vector_out_path):
            print(vector_out_path, "exists, skip")
            continue

        try:
            vector_obj = wrap_shape(vector_path)
            vector_obj.clip(vector_obj.layer, extent_geom)
            vector_obj.write(vector_obj.layer_clip, vector_out_path)

        except Exception as e:
            print(e)
