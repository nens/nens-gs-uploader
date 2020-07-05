"""#
Created on Fri Apr 26 16:39:50 2019

@author: chris.kerklaan

Vector wrapper used for GIS programming
"""
# System imports
import os

# Third party imports
import osr
import ogr
import gdal
import rtree
from tqdm import tqdm

# Global DRIVERS
DRIVER_GDAL_MEM = gdal.GetDriverByName("MEM")
DRIVER_OGR_SHP = ogr.GetDriverByName("ESRI Shapefile")
DRIVER_OGR_GPKG = ogr.GetDriverByName("GPKG")
DRIVER_OGR_MEM = ogr.GetDriverByName("Memory")
_mem_num = 0

# Shapes
POLYGON = "POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"
POINT = "POINT ({x1} {y1})"
SHP_EXTENSIONS = ["shp", "prj", "dbf", "cpg", "qpj", "shx"]

# Exceptions
ogr.UseExceptions()


class vector(object):
    """wrapper of ogr vector"""

    def __init__(self, ds, id=10, layer_name=None, epsg=28992):

        if type(ds) is str:
            self.ds = ogr.Open(ds, 1)
        # elif type(ds) is dict:
        #     self.ds = ogr.Open(connect2pg_database(ds), 1)
        else:
            self.ds = ds

        if not layer_name:
            self.layer = self.ds[0]
            self.layer_defn = self.layer.GetLayerDefn()
        else:
            self.layer = self.ds.GetLayer(layer_name)
            self.layer_defn = self.layer.GetLayerDefn()

        self.layers = [layer.GetName() for layer in self.ds]
        self.info(self.layer)

    # def __iter__(self):
    #     for count in range(self.layer.GetFeatureCount()):
    #         yield self.layer[count]

    def info(self, layer):

        self.layer = layer
        self.layer_defn = self.layer.GetLayerDefn()

        self.sr = self.layer.GetSpatialRef()
        self.layer.ResetReading()
        self.geom_type = self.layer.GetGeomType()
        self.count = self.layer.GetFeatureCount()

        self.field_names = []
        for i in range(self.layer_defn.GetFieldCount()):
            self.field_names.append(self.layer_defn.GetFieldDefn(i).GetName())

    def reset(self):
        self.layer.ResetReading()

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
        self.layer.SetSpatialFilter(geometry)

    def set_attribute_filter(self, string):
        self.layer.SetAttributeFilter(string)

    def add_field(self, name, ogr_type):
        defn = ogr.FieldDefn(name, ogr_type)
        self.layer.CreateField(defn)
        self.info(self.layer)

    def add_fields(self, attributes):
        for key, value in attributes.items():
            self.layer.CreateField(ogr.FieldDefn(key, value))

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

    def copy_shell(self, layer_name="mem", geom_type=ogr.wkbPolygon):
        return copymem(self.layer, layer_name="mem", geom_type=geom_type)

    def copy(self, layer_name="mem", geom_type=ogr.wkbPolygon):
        ds, layer = copymem(self.layer, layer_name="mem", geom_type=geom_type)
        for feature in self.layer:
            layer.CreateFeature(feature)
        return ds, layer

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

    def delete_fields(self, field_name_list):
        for field_name in field_name_list:
            self.layer.DeleteField(self.layer.FindFieldIndex(field_name, 0))

    def copy_datasource(self, out_layer):
        """ copy layer from in_file """
        self.out_datasource = DRIVER_OGR_SHP.CopyDataSource(self.ds, out_layer)
        self.out_layer = self.out_datasource[0]
        self.layer.ResetReading()

    def set_field(self, feature_number, field_name, field_value):
        """ Set a field value based on a feature number. """
        feature = self.layer.GetFeature(feature_number)
        field_num = self.layer.FindFieldIndex(field_name, 1)
        feature.SetField(field_num, field_value)
        self.layer.SetFeature(feature)
        feature = None

    def query(self, geometry):
        """ Return generator of features with geometry as spatial filter. """
        self.layer.SetSpatialFilter(geometry)
        for feature in self.layer:
            yield feature
        self.layer.SetSpatialFilter(None)

    def close(self):
        self.layer = None
        self.ds = None

    def lower_all_field_names(self):
        for field_defn in self.get_field_defns():
            field_defn.SetName(field_defn.GetName().lower())

    def get_geom_transform(self, out_epsg=28992):

        out_spatial_ref = osr.SpatialReference()
        out_spatial_ref.ImportFromEPSG(out_epsg)

        coordTrans = osr.CoordinateTransformation(self.sr, out_spatial_ref)

        return coordTrans

    def rasterize(
        self, rows, columns, geotransform, nodata=-9999, options=None
    ):
        target_ds = DRIVER_GDAL_MEM.Create(
            "ras.tif", columns, rows, 1, gdal.GDT_Int16
        )

        band = target_ds.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        band.Fill(nodata)
        band.FlushCache()
        target_ds.SetProjection(self.sr.ExportToWkt())
        target_ds.SetGeoTransform(geotransform)

        if options:
            gdal.RasterizeLayer(target_ds, [1], self.layer, options=options)
        else:
            gdal.RasterizeLayer(target_ds, (1,), self.layer, burn_values=(1,))

        array = target_ds.ReadAsArray()
        target_ds = None

        return array

    def write(
        self,
        path_name,
        ogr_layer=None,
        layer_name="vect",
        epsg=28992,
        geom_type=None,
    ):
        if not ogr_layer:
            ogr_layer = self.layer

        self.get_spatial_reference(epsg=epsg)
        self.layer_defn = ogr_layer.GetLayerDefn()
        if not geom_type:
            geom_type = ogr_layer.GetGeomType()

        if os.path.splitext(path_name)[1] == ".gpkg":
            data_source = DRIVER_OGR_GPKG.CreateDataSource(path_name)
        else:
            data_source = DRIVER_OGR_SHP.CreateDataSource(path_name)

        out_layer = data_source.CreateLayer(layer_name, self.sr, geom_type)

        for i in range(self.layer_defn.GetFieldCount()):
            out_layer.CreateField(self.layer_defn.GetFieldDefn(i))

        ogr_layer.ResetReading()
        for feat in ogr_layer:
            out_layer.CreateFeature(feat)
            feat = None

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

    def append_feature(self, geometry, attributes):
        append_feature(self.layer, self.layer_defn, geometry, attributes)

    def change_source(self, in_ds, in_layer):
        self.ds = None
        self.layer = None
        self.ds = in_ds
        self.layer = in_layer

    def correct(self, layer, name="", epsg=28992):
        self.ds_correct = correct(layer, layer_name=name, epsg=epsg)
        self.layer_correct = self.ds_correct[0]
        self.change_source(self.ds_correct, self.layer_correct)

    def clip(self, layer, clip_geom):
        self.ds_clip = clip(layer, clip_geom)
        self.layer_clip = self.ds_clip[0]
        self.change_source(self.ds_clip, self.layer_clip)

    def buffer(self, layer, buffer_size):
        self.ds_buffer = buffer(layer, buffer_size)
        self.layer_buffer = self.ds_buffer[0]
        self.change_source(self.ds_buffer, self.layer_buffer)

    def dissolve(self, layer, value=None):
        self.ds_dissolve = dissolve(layer, value)
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


def get_data(vector_layer):
    data = {}
    for fid in range(vector_layer.GetFeatureCount()):
        feature = vector_layer[fid]
        count = 0
        if feature:
            count = +1
            if count == 1:
                for key in feature.keys():
                    data[key] = []
            for key in feature.keys():
                data[key].append(feature[key])

    return data


class FooMeta(type):
    def __iter__(self):
        return self.by_id.iteritems()


def create_file(
    path, layer_name, geom_type, epsg=28992, ogr_driver="ESRI Shapefile"
):
    """ from scratch"""
    ogr_driver = ogr.GetDriverByName(ogr_driver)
    ds = ogr_driver.CreateDataSource(path)
    layer = ds.CreateLayer(layer_name, geom_type=geom_type)
    create_prj_file(path.replace(".shp", ".prj"), epsg=epsg)
    return ds, layer


def create_prj_file(path, epsg=28992):
    spatialRef = osr.SpatialReference()
    spatialRef.ImportFromEPSG(epsg)
    spatialRef.MorphToESRI()
    file = open(path, "w")
    file.write(spatialRef.ExportToWkt())
    file.close()


def create_mem_ds():
    global _mem_num
    mem_datasource = DRIVER_OGR_MEM.CreateDataSource(
        "/vsimem/mem{}".format(_mem_num)
    )
    _mem_num = _mem_num + 1
    return mem_datasource


def create_mem_layer(layer_name, geom_type, epsg):
    ds = create_mem_ds()
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(epsg)
    layer = ds.CreateLayer(layer_name, sr, geom_type=geom_type)
    return ds, layer


def geom_transform(in_spatial_ref, out_epsg):
    out_spatial_ref = osr.SpatialReference()
    out_spatial_ref.ImportFromEPSG(out_epsg)
    coordTrans = osr.CoordinateTransformation(in_spatial_ref, out_spatial_ref)
    return coordTrans


def create_index(layer):
    layer.ResetReading()
    index = rtree.index.Index(interleaved=False)
    for fid1 in range(0, layer.GetFeatureCount()):
        feature1 = layer.GetFeature(fid1)
        geometry1 = feature1.GetGeometryRef()
        xmin, xmax, ymin, ymax = geometry1.GetEnvelope()
        index.insert(fid1, (xmin, xmax, ymin, ymax))
    return index


def remove_shape_if_exists(path):
    if os.path.exists(path):
        for extension in SHP_EXTENSIONS:
            remove_file = path.replace("shp", extension)
            if os.path.exists(remove_file):
                os.remove(remove_file)


def copymem(vector_layer, layer_name="mem", geom_type=ogr.wkbPolygon):
    out_datasource = create_mem_ds()
    out_layer = out_datasource.CreateLayer(
        layer_name, vector_layer.GetSpatialRef(), geom_type
    )

    vector_layer_defn = vector_layer.GetLayerDefn()
    for i in range(vector_layer_defn.GetFieldCount()):
        out_layer.CreateField(vector_layer_defn.GetFieldDefn(i))

    out_layer = None
    return out_datasource


def multipoly2poly(in_layer, out_layer):

    lost_features = []
    layer_defn = in_layer.GetLayerDefn()
    field_names = []
    for n in range(layer_defn.GetFieldCount()):
        field_names.append(layer_defn.GetFieldDefn(n).name)

    for count, in_feat in enumerate(in_layer):
        content = {}
        for field_name in field_names:
            content[field_name] = in_feat.GetField(field_name)

        geom = in_feat.GetGeometryRef()
        if geom == None:
            print("warning", "FID {} has no geometry.".format(count))
            lost_features.append(in_feat.GetFID())
            continue

        if (
            geom.GetGeometryName() == "MULTIPOLYGON"
            or geom.GetGeometryName() == "MULTILINESTRING"
        ):
            for geom_part in geom:
                add_polygon(geom_part.ExportToWkb(), content, out_layer)
        else:
            add_polygon(geom.ExportToWkb(), content, out_layer)

    return lost_features


def add_polygon(simple_polygon, content, out_lyr):
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
    feature = None
    return layer


def multiparts_to_singleparts(vector_layer):
    out_datasource, out_layer = copymem(vector_layer, geom_type=ogr.wkbPolygon)
    multipoly2poly(vector_layer, out_layer)
    out_layer = None
    return out_datasource


def overlap(layer):
    """
    The function returns overlapping geometries 

    Parameters
    ----------
    layer : OGR LAYER

    Returns
    -------
    overlap: dict {FID: [intersecting FIDS]}
    non_overlap: list [FIDS]

    """

    overlap_list = []
    non_overlap_list = []

    idx = create_index(layer)

    layer.ResetReading()
    for feature in tqdm(layer):
        fid = feature.GetFID()
        geometry = feature.geometry().Clone()
        intersect_list = [i for i in idx.intersection(geometry.GetEnvelope())]

        if len(intersect_list) > 1:
            overlap_list.append(sorted(intersect_list))
        else:
            non_overlap_list.append(fid)

    frozen_set_list = list(set(frozenset(x) for x in tqdm(overlap_list)))
    unique_list = list(list(x) for x in frozen_set_list)

    return unique_list, non_overlap_list


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

    geom_type = geometry.GetGeometryType()

    # check pointcount if linestring
    if geom_type == ogr.wkbLineString:
        if geometry.GetPointCount() == 1:
            print("Geometry point count of linestring = 1")
            return geometry, False
        else:
            pass

    # check self intersections
    if geom_type == ogr.wkbPolygon:
        geometry = geometry.Buffer(0)

    # check slivers
    if not geometry.IsValid():
        perimeter = geometry.Boundary().Length()
        area = geometry.GetArea()
        sliver = float(perimeter / area)

        if sliver < 1:
            wkt = geometry.ExportToWkt()
            geometry = ogr.CreateGeometryFromWkt(wkt)

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

        # Get inspatial reference and geometry from in shape
        geom_type = in_layer.GetGeomType()
        in_spatial_ref = in_layer.GetSpatialRef()
        in_layer.ResetReading()

        mem_datasource = create_mem_ds()

        mem_layer = mem_datasource.CreateLayer(
            layer_name, in_spatial_ref, geom_type
        )

        layer_defn = in_layer.GetLayerDefn()
        for i in range(layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(i)
            mem_layer.CreateField(field_defn)

        print("info", "check - Multipart to singlepart")
        lost_feat = multipoly2poly(in_layer, mem_layer)
        lost_features = lost_features + lost_feat

        if mem_layer.GetFeatureCount() == 0:
            print("error", "Multipart to singlepart failed")
            return 1

        spatial_ref_3857 = osr.SpatialReference()
        spatial_ref_3857.ImportFromEPSG(int(epsg))
        reproject = osr.CoordinateTransformation(
            in_spatial_ref, spatial_ref_3857
        )

        flatten = False
        geom_name = ogr.GeometryTypeToName(geom_type)
        if "3D" in geom_name:
            print("warning", "geom type: " + geom_name)
            print("info", "Flattening to 2D")
            flatten = True

        elif geom_type < 0:
            print("error", "geometry invalid, most likely has a z-type")
            raise ValueError(
                "geometry invalid, most likely has a z-type",
                "geom type: ",
                geom_name,
            )

        # Create output dataset and force dataset to multiparts
        if geom_type == 6:
            geom_type = 3  # polygon

        elif geom_type == 5:
            geom_type = 2  # linestring

        elif geom_type == 4:
            geom_type = 1  # point

        out_datasource = create_mem_ds()
        out_layer = out_datasource.CreateLayer(
            layer_name, spatial_ref_3857, geom_type
        )
        layer_defn = in_layer.GetLayerDefn()

        # Copy fields from memory layer to output dataset
        for i in range(layer_defn.GetFieldCount()):
            out_layer.CreateField(layer_defn.GetFieldDefn(i))

        print("info", "check - Reproject layer to {}".format(str(epsg)))
        for out_feat in tqdm(mem_layer):
            out_geom = out_feat.GetGeometryRef()

            try:
                out_geom, valid = fix_geometry(out_geom)
            except Exception as e:
                print(e)
                print(out_feat.GetFID())
            if not valid:
                print("warning", "geometry invalid even with buffer, skipping")
                lost_features.append(out_feat.GetFID())
                continue

            # Force and transform geometry
            out_geom = ogr.ForceTo(out_geom, geom_type)
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
            print(
                "warning",
                "Lost {} features during corrections".format(
                    len(lost_features)
                ),
            )
            print("warning", "FIDS: {}".format(lost_features))

        elif in_feature_count > out_feature_count:
            print("warning", "In feature count greater than out feature count")

        else:
            pass

    except Exception as e:
        print(e)

    finally:
        mem_layer = None
        mem_datasource = None
        out_layer = None

        print("Finished vector corrections")
    return out_datasource


def dissolve(vector_layer, field=None, simplify=0):
    """
    Dissolved the vector layer into a single multipolygon feature.
    Value can be filled to used certain field.

    Parameters
    ----------
    vector_layer : ogr vector
    value: str

    Returns
    -------
    out_datasource : ogr datasource

    """

    vector_layer.ResetReading()
    out_datasource = copymem(
        vector_layer,
        layer_name="dissolve",
        geom_type=vector_layer.GetGeomType(),
    )
    out_layer = out_datasource[0]
    out_layer_defn = out_layer.GetLayerDefn()

    if field:
        unique_dict = {}
        for fid in range(0, vector_layer.GetFeatureCount()):
            feature = vector_layer[fid]
            field_name = feature[field]
            if not field_name in unique_dict:
                unique_dict[field_name] = [fid]
            else:
                unique_dict[field_name].append(fid)

        for field_value, fid_list in tqdm(unique_dict.items()):
            multi = ogr.Geometry(ogr.wkbMultiPolygon)
            for fid in fid_list:
                feature = vector_layer[fid]
                geometry = feature.GetGeometryRef()
                geometry.CloseRings()
                wkt = geometry.ExportToWkt()
                multi.AddGeometryDirectly(ogr.CreateGeometryFromWkt(wkt))

            union = multi.UnionCascaded()
            append_feature(out_layer, out_layer_defn, union, feature.items())
    else:
        multi = ogr.Geometry(ogr.wkbMultiPolygon)
        for fid in tqdm(range(0, vector_layer.GetFeatureCount())):
            feature = vector_layer[fid]
            geometry = feature.geometry()
            if geometry:
                if geometry.GetGeometryType() > 3:  # multipolygon
                    for single_geom in geometry:
                        single_geom.CloseRings()
                        wkt = single_geom.ExportToWkt()
                        multi.AddGeometryDirectly(
                            ogr.CreateGeometryFromWkt(wkt)
                        )
                else:
                    geometry.CloseRings()
                    wkt = geometry.ExportToWkt()
                    multi.AddGeometryDirectly(ogr.CreateGeometryFromWkt(wkt))

        union = multi.UnionCascaded()
        append_feature(out_layer, out_layer_defn, union, feature.items())

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

    out_datasource = copymem(vector_layer, geom_type=vector_layer_geom_type)
    out_layer = out_datasource[0]
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
                            if (
                                geom_part.GetGeometryType()
                                == vector_layer_geom_type
                            ):
                                vector_geom, valid = fix_geometry(geom_part)

                    else:
                        name = ogr.GeometryTypeToName(diff_part_type)
                        print("Found foreign geometry:", name)
                        continue

                else:
                    vector_geom, valid = fix_geometry(difference)

            else:
                pass

        out_layer = append_feature(
            out_layer, vector_layer_defn, vector_geom, vector_feat.items()
        )

    out_layer = None
    return out_datasource


def buffer(in_layer, buffer_size):
    """
    Buffers all in_layer geometries .

    Parameters
    ----------
    in_layer : ogr layer
    buffer : integer or float

    Returns
    -------
    out_datasource : ogr datasource

    """

    in_layer_geom_type = in_layer.GetGeomType()
    in_layer.ResetReading()

    out_datasource = copymem(in_layer, geom_type=in_layer_geom_type)
    out_layer = out_datasource[0]

    print("starting buffer")
    for out_feat in tqdm(in_layer):
        out_geom = out_feat.GetGeometryRef().Buffer(buffer_size)
        out_feat.SetGeometry(out_geom)
        out_layer.CreateFeature(out_feat)

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

    out_datasource = copymem(in_layer, geom_type=in_layer_geom_type)
    out_layer = out_datasource[0]

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


def merge_directory(vector_path_list, simplify=0):

    if type(vector_path_list[0]) == str:
        ds = ogr.Open(vector_path_list[0])
    else:
        ds = vector_path_list[0]

    layer = ds[0]
    out_datasource = copymem(layer)
    out_layer = out_datasource[0]

    # print('appending', file)
    for file in tqdm(vector_path_list):
        if type(file) == str:
            ds = ogr.Open(file)
        else:
            ds = file
        if ds is None:
            print("This is None")
            continue

        layer = ds[0]
        layer_defn = layer.GetLayerDefn()
        for fid in range(0, layer.GetFeatureCount()):
            feat = layer[fid]
            geometry = feat.GetGeometryRef().Clone()
            geometry = geometry.Simplify(simplify)
            attributes = feat.items()
            append_feature(out_layer, layer_defn, geometry, attributes)

    return out_datasource, out_layer


def vector_to_geom(extent_path, epsg=28992):
    extent_vector = vector(extent_path)
    extent_vector.correct(extent_vector.layer, epsg=epsg)
    extent_vector.dissolve(extent_vector.layer)
    extent_feature = extent_vector.layer[0]
    extent_geom = extent_feature.GetGeometryRef()
    extent_geom = extent_geom.Buffer(0)
    return extent_geom


def vector_to_envelope_geom(extent_path, epsg=28992):
    geom = vector_to_geom(extent_path, epsg=epsg)
    x1, x2, y1, y2 = geom.GetEnvelope()
    wkt = POLYGON.format(x1=x1, x2=x2, y1=y1, y2=y2)
    geom = ogr.CreateGeometryFromWkt(wkt)
    return geom


def reproject(geom, in_epsg, out_epsg):
    spatial_ref = osr.SpatialReference()
    spatial_ref.ImportFromEPSG(int(in_epsg))
    spatial_ref_out = osr.SpatialReference()
    spatial_ref_out.ImportFromEPSG(int(out_epsg))

    translate = osr.CoordinateTransformation(spatial_ref, spatial_ref_out)
    return geom.Transform(translate)


if __name__ == "__main__":
    pass
