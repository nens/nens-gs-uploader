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
from core.pyconnectsql import connect2pg
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


PG_DATABASE = {
    "STAGING": pg_staging,
    "PRODUCTIE_KLIMAATATLAS": pg_atlas,
    "PRODUCTIE_KLIMAATATLAS_V1": pg_atlas_v1,
    "PRODUCTIE_LIZARD": pg_lizard,
    "PROJECTEN_KLIMAATATLAS": pg_project_atlas,
    "PROJECTEN_LIZARD": pg_project_lizard,
    "PRODUCTIE_FLOODING": pg_flooding,
}


def check_ogr_columns(ds, layer):
    """
    Checks if ogr column values are compatible with postgis, alters 
    to None when needed.     

    Parameters
    ----------
    ds : OGR datasource
    layer : OGR Layer

    Returns
    -------
    ds : OGR datasource
    layer: OGR Layer

    """
    layer.ResetReading()

    for feature in layer:
        for key, value in feature.items().items():
            if "/" in str(value):
                feature[key] = None
                layer.SetFeature(feature)

    return ds, layer


def connect2pg_database(database, con_type="ogr"):
    """ Returns connection to a postgresdatabase. """
    connection = connect2pg(
        dbname=database["database"],
        port=database["port"],
        host=database["host"],
        user=database["username"],
        password=database["password"],
    )
    if con_type == "ogr":
        return connection.ogr_connection()
    else:
        return connection


def copy2pg_database(ds, ds_layer, layer, layer_name, schema="public", overwrite="YES"):

    # ds, layer = check_ogr_columns(ds_layer, layer)

    options = [
        "OVERWRITE={}".format(overwrite),
        "SCHEMA={}".format(schema),
        "SPATIAL_INDEX=GIST",
        "FID=ogc_fid",
        "PRECISION=NO",
    ]
    try:
        geom_type = layer.GetGeomType()

        ogr.RegisterAll()
        new_layer = ds.CreateLayer(
            layer_name, layer.GetSpatialRef(), geom_type, options
        )
        for x in range(layer.GetLayerDefn().GetFieldCount()):
            new_layer.CreateField(layer.GetLayerDefn().GetFieldDefn(x))

        layer.ResetReading()
        new_layer.StartTransaction()
        for fid in tqdm(range(layer.GetFeatureCount())):
            #try:
                new_feature = layer.GetFeature(fid)
                new_feature.SetFID(-1)
                new_layer.CreateFeature(new_feature)
                if fid % 128 == 0:
                    new_layer.CommitTransaction()
                    new_layer.StartTransaction()
            #except Exception as e:
            #    print("Got exception", e, "skipping feature")

        new_layer.CommitTransaction()

    except Exception as e:
        print("Got exception", e, "trying copy layer")

        new_layer = ds.CopyLayer(layer, layer_name, options)

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


def _clear_connections_database(database, client_adress="10.100.230.131"):
    connection = connect2pg_database(database, "psycopg")
    query_check_1 = "SET extra_float_digits = 3"
    query_check_2 = "ROLLBACK"
    sql = """
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE
    datname = '{}'  and client_addr = '{}' and query = '{}' or query = '{}'
    ;
    """.format(
        database["database"], client_adress, query_check_1, query_check_2
    )

    connection.execute_sql(sql)


if __name__ == "__main__":
    import sys

    sys.path.append("C:/Users/chris.kerklaan/tools")
    inifile = "C:/Users/chris.kerklaan/tools/instellingen/meerdijk/nens_gs_uploader.ini"
