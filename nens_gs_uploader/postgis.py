# -*- coding: utf-8 -*-
"""
Created on Mon Jul 15 18:30:37 2019

@author: chris.kerklaan - N&S
"""
# Sytem imports
import sys

# Third-party imports
import osr    
import ogr
    
# Local imports
from nens_gs_uploader.pyconnectsql import connect2pg

## 
sys.path.append("C:/Users/chris.kerklaan/Documents/base_modules")
from sql_base.localsecret import (
        production_klimaatatlas     as pg_atlas,
        staging                     as pg_staging,
        production_lizard           as pg_lizard,
        project_klimaatatlas        as pg_project_lizard,
        project_lizard              as pg_project_atlas,
        production_klimaatatlas_v1  as pg_atlas_v1        
        )

# Exceptions
ogr.UseExceptions()

# Global within script
SERVERS = {
    "STAGING": "https://maps2.staging.lizard.net/geoserver/rest",
    "PRODUCTIE_KLIMAATATLAS": "https://maps1.klimaatatlas.net/geoserver/rest/", 
    "PRODUCTIE_LIZARD": "https://geoserver9.lizard.net/geoserver/rest/",
    "PROJECTEN_KLIMAATATLAS":"https://maps1.project.lizard.net/geoserver/rest/",
    "PROJECTEN_LIZARD":"https://maps1.project.lizard.net/geoserver/rest/"
    }

PG_DATABASE = {
    "STAGING": pg_staging,
    "PRODUCTIE_KLIMAATATLAS": pg_atlas, 
    "PRODUCTIE_KLIMAATATLAS_V1": pg_atlas_v1, 
    "PRODUCTIE_LIZARD": pg_lizard,
    "PROJECTEN_KLIMAATATLAS": pg_project_atlas,
    "PROJECTEN_LIZARD": pg_project_lizard
    }

def connect2pg_database(database):
    """ Returns connection to a postgresdatabase. """
    connection = connect2pg(dbname   = database["database"],
                            port     = database["port"],
                            host     = database["host"],
                            user     = database["username"],
                            password = database["password"])   
    return connection.ogr_connection()

def copy2pg_database(database, in_layer, layer_name):
    try:    
        out_layer = database.datasource.CopyLayer(in_layer,
                                                  layer_name,
                                                  ["OVERWRITE=YES",
                                                   "SCHEMA=public",
                                                   "SPATIAL_INDEX=GIST",
                                                   "FID=ogc_fid"])
        if out_layer.GetFeatureCount() == 0:
            raise ValueError("Postgres vector feature count is 0")
            
    except Exception as e:
        print(e)
        print("try copying manually")
        
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(3857)
        feature = in_layer[0]
        geom =  feature.GetGeometryRef()
        geom_type = geom.GetGeometryType()
        
        out_layer =  database.datasource.CreateLayer(
                                                    layer_name, 
                                                    srs, 
                                                    geom_type, 
                                                    ['OVERWRITE=YES'])
        out_layer.StartTransaction()
        # define all fields
        in_layer_defn = in_layer.GetLayerDefn()
        for i in range(in_layer_defn.GetFieldCount()):
                field_defn = in_layer_defn.GetFieldDefn(i)
                out_layer.CreateField(field_defn)
        
        
        for in_feature in in_layer:
            out_feature = ogr.Feature(in_layer_defn)
            out_feature.SetGeometry(in_feature.GetGeometryRef())
            out_layer.CreateFeature(out_feature)
            feature = None

        out_layer.CommitTransaction()
        database.datasource.StartTransaction()
        database.datasource.ExecuteSQL('CREATE INDEX idx ON "{}"'
                'USING GIST (wkb_geometry);'.format(layer_name))
        database.datasource.CommitTransaction()  
    
    finally:
        if out_layer.GetFeatureCount() == 0:
            raise ValueError("Postgres vector feature count is 0")
            
        out_layer = None
      
def add_metadata_pgdatabase(setting, database):
    
    metadata_layer = database.datasource.GetLayer('metadata')
    
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
         
    
    