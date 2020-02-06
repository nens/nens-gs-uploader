# -*- coding: utf-8 -*-
"""#
Created on Mon Jul 15 18:30:37 2019

@author: chris.kerklaan - N&S
"""
# Third-party imports
from tqdm import tqdm
import ogr
import gdal

# Local imports
from nens_gs_uploader.pyconnectsql import connect2pg
from nens_gs_uploader.localsecret.localsecret import (
    production_klimaatatlas as pg_atlas,
    staging as pg_staging,
    production_lizard as pg_lizard,
    project_klimaatatlas as pg_project_lizard,
    project_lizard as pg_project_atlas,
    production_klimaatatlas_v1 as pg_atlas_v1,
    production_flooding as pg_flooding,
)

# Exceptions
ogr.UseExceptions()

# Progress bar
progress = gdal.TermProgress_nocb

# Global within script
REST = {
    "STAGING": "https://maps2.staging.lizard.net/geoserver/rest/",
    "PRODUCTIE_KLIMAATATLAS": "https://maps1.klimaatatlas.net/geoserver/rest/",
    "PRODUCTIE_FLOODING": "https://flod-geoserver1.lizard.net/geoserver/rest/",
    "PRODUCTIE_LIZARD": "https://geoserver9.lizard.net/geoserver/rest/",
    "PROJECTEN_KLIMAATATLAS": "https://maps1.project.lizard.net/geoserver/rest/",
    "PROJECTEN_LIZARD": "https://maps1.project.lizard.net/geoserver/rest/",
}
SERVERS = {
    "STAGING": "https://maps2.staging.lizard.net/geoserver/",
    "PRODUCTIE_KLIMAATATLAS": "https://maps1.klimaatatlas.net/geoserver/",
    "PRODUCTIE_FLOODING": "https://flod-geoserver1.lizard.net/geoserver/",
    "PRODUCTIE_LIZARD": "https://geoserver9.lizard.net/geoserver/",
    "PROJECTEN_KLIMAATATLAS": "https://maps1.project.lizard.net/geoserver/",
    "PROJECTEN_LIZARD": "https://maps1.project.lizard.net/geoserver/",
}

PG_DATABASE = {
    "STAGING": pg_staging,
    "PRODUCTIE_KLIMAATATLAS": pg_atlas,
    "PRODUCTIE_KLIMAATATLAS_V1": pg_atlas_v1,
    "PRODUCTIE_LIZARD": pg_lizard,
    "PROJECTEN_KLIMAATATLAS": pg_project_atlas,
    "PROJECTEN_LIZARD": pg_project_lizard,
    "PRODUCTIE_FLOODING": pg_flooding,
}


def connect2pg_database(database):
    """ Returns connection to a postgresdatabase. """
    connection = connect2pg(
        dbname=database["database"],
        port=database["port"],
        host=database["host"],
        user=database["username"],
        password=database["password"],
    )
    return connection.ogr_connection()


def copy2pg_database(datasource, in_layer, layer_name, schema="public"):
    options = [
        "OVERWRITE=YES",
        "SCHEMA={}".format(schema),
        "SPATIAL_INDEX=GIST",
        "FID=ogc_fid",
        "PRECISION=NO",
    ]
    try:
        geom_type = in_layer.GetGeomType()

        ogr.RegisterAll()
        new_layer = datasource.CreateLayer(
            layer_name, in_layer.GetSpatialRef(), geom_type, options
        )
        for x in range(in_layer.GetLayerDefn().GetFieldCount()):
            new_layer.CreateField(in_layer.GetLayerDefn().GetFieldDefn(x))

        #             shape.write(datasource[0],"C:/Users/chris.kerklaan/Documents/Projecten/westland/clip_test5.shp")
        in_layer.ResetReading()
        new_layer.StartTransaction()
        for fid in tqdm(range(in_layer.GetFeatureCount())):
            try:
                new_feature = in_layer.GetFeature(fid)
                new_feature.SetFID(-1)
                new_layer.CreateFeature(new_feature)
                if x % 128 == 0:
                    new_layer.CommitTransaction()
                    new_layer.StartTransaction()
            except Exception as e:
                print("Got exception", e, "skipping feature")

        new_layer.CommitTransaction()

    except Exception as e:
        print("Got exception", e, "trying copy layer")

        new_layer = datasource.CopyLayer(in_layer, layer_name, options)

    finally:
        if new_layer.GetFeatureCount() == 0:
            raise ValueError("Postgres vector feature count is 0")
        new_layer = None


def add_metadata_pgdatabase(setting, datasource):

    metadata_layer = datasource.GetLayer("metadata")

    # if exists delete
    metadata_layer.StartTransaction()
    for feature in metadata_layer:
        if feature.GetField("pg_layer") == setting.layer_name:
            metadata_layer.DeleteFeature(feature.GetFID())
    metadata_layer.CommitTransaction()

    metadata_layer.StartTransaction()
    metadata_layer_defn = metadata_layer.GetLayerDefn()
    new_feature = ogr.Feature(metadata_layer_defn)
    for key, value in setting.metadata.items():
        new_feature.SetField(key, value)
    metadata_layer.CreateFeature(new_feature)
    metadata_layer.CommitTransaction()


if __name__ == "__main__":
    import sys

    sys.path.append("C:/Users/chris.kerklaan/tools")
    inifile = "C:/Users/chris.kerklaan/tools/instellingen/meerdijk/nens_gs_uploader.ini"
