# -*- coding: utf-8 -*-
"""
Created on Wed Jul 24 15:39:13 2019

@author: chris.kerklaan - N&S

Dit script kan uploaden naar de Geoservers van N&S.
Er zijn meerdere opties:
    1. Uploaden vanaf een vector bestand op een schijf
    2. Uploaden vanaf een postgres tabel 
    3. Overzetten van de ene geoserver naar de andere -- moet nog ontwikkeld worden.


Je kan ook WMS lagen hiermee uploaden naar Lizard.

TODOs:
    0. BELANGRIJK: TEST SCHRIJVEN VOOR BASIS FUNCTIONALITEITEN
    3. Output verbeteren
    5. Warning voor het aantal kolommen

    
NOTES:
    1. Geoserver 9 is ouder dan de rest, hierdoor werkt upload naar geoserver 9 niet met styling

"""
# system imports
import os
import sys
import json
import logging
from time import sleep
from configparser import RawConfigParser

# Third-party imports
import ogr
import gdal
import argparse
from glob import glob

# Test arguments
inifile = (
    "C:/Users/chris.kerklaan/tools/instellingen/flevoland/nens_gs_uploader.ini"
)
sys.path.append("C:/Users/chris.kerklaan/tools")
del sys.path[0]

# Local imports
from nens_gs_uploader.postgis import (
    PG_DATABASE,
    copy2pg_database,
    add_metadata_pgdatabase,
)
from nens_gs_uploader.project import (
    logger,
    log_time,
    percentage,
    print_list,
    print_dictionary,
)
from nens_gs_uploader.vector import vector_to_geom, wrap_shape
from nens_gs_uploader.wrap import wrap_geoserver, REST
from nens_gs_uploader.sld import wrap_sld
from nens_gs_uploader.wmslayers import wmslayers
from nens_gs_uploader.postgis import _clear_connections_database

# Exceptions
ogr.UseExceptions()
gdal.UseExceptions()

# GDAL configuration options
gdal.SetConfigOption("CPL_DEBUG", "ON")
gdal.SetConfigOption("CPL_ERROR", "ON")
gdal.SetConfigOption("CPL_CURL_VERBOSE", "ON")

# Logging configuration options
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inifile", metavar="INIFILE", help="Settings voor inifile."
    )
    return parser


def has_numbers(string):
    return any(char.isdigit() for char in string)


def lower_string(string):
    return string.lower().replace(" ", "").replace("-", "_")


def get_subject_from_name(name, organisation):
    relevant = []
    for count, part in enumerate(name.split("_")):
        is_organisation = organisation in part
        if (count == 0) and (not has_numbers(part)) and (not is_organisation):
            relevant.append(part)
        elif not is_organisation:
            relevant.append(part)
        else:
            pass

    return "_".join(relevant)


def get_subject_from_path(path, organisation):
    return get_subject_from_name(
        os.path.basename(path).split(".")[0], organisation
    )


def get_paths_and_subjects(setting, source):
    if source == "directory":
        in_paths = glob(setting.directory + "/*.shp")
        in_paths = in_paths + glob(setting.directory + "/*.gpkg")
        subjects = [
            get_subject_from_path(in_path, setting.organisatie)
            for in_path in in_paths
        ]

    elif source == "postgis":
        in_paths = setting.config.sections()[6:]
        subjects = setting.get_postgis_subjects()
    else:
        print("choose source")

    if setting.wms_layer_only:
        in_paths = glob(setting.directory + "/*.json")
        subjects = [
            get_subject_from_path(in_path, setting.organisatie)
            for in_path in in_paths
        ]
    return in_paths, subjects


def set_log_config(location, name="log"):
    path = os.path.join(location, name)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=path + ".log",
        level=logging.DEBUG,
    )
    gdal.SetConfigOption("CPL_LOG_ERRORS", path + "_gdal_err.log")
    gdal.SetConfigOption("CPL_LOG", path + "_gdal.log")


class settings_object(object):
    """Reads settings from inifile settings from command line tool"""

    def __init__(self, ini_file=None, postgis=True, folder=True):
        if ini_file is not None:
            if not os.path.exists(inifile):
                raise ValueError("path does not exist")

            config = RawConfigParser()
            config.read(ini_file)
            self.ini = ini_file
            self.ini_location = os.path.dirname(ini_file)
            self.config = config

            self.set_project()

    def add(self, key, value):
        setattr(self, key, value)

    def get_postgis_subjects(self):
        subjects = []
        for section in self.config.sections()[5:]:
            for i in self.config.items(section):
                if i[0] == "out_layer":
                    subjects.append(i[1])

        return subjects

    def set_project(self):
        self.set_values("project")
        self.set_values("input_directory")
        self.set_values("tool")
        self.set_values("input_styling")

    def set_postgis(self):
        self.set_values("input_postgis")

    def set_directory(self):
        self.set_values("input_directory")

    def set_values(self, section):
        for key in self.config[section]:
            value = self.config[section][key]
            if value == "True":
                value = True
            elif value == "False":
                value = False
            else:
                pass

            self.key = value
            setattr(self, key, value)

    def postgis_sld_generator(self):
        for layer in self.config.items("input_postgis"):
            if "style" in layer[0]:
                yield layer[1]


def add_output_settings(setting, onderwerp, in_path):
    """ Returns geoserver settings in an organized manner
    conform https://sites.google.com/nelen-schuurmans.nl/handleiding-klimaatatlas/data-protocol
    """

    onderwerp = lower_string(onderwerp)

    # layer names, workspace names en server names
    if "PRODUCTIE" in setting.server_naam:
        layer_name = "{}_{}_{}".format(
            setting.bo_nummer, setting.organisatie, onderwerp
        )
        workspace_name = setting.organisatie + "_" + setting.product_naam
    elif (
        "PROJECTEN" in setting.server_naam or "STAGING" in setting.server_naam
    ):
        layer_name = "{}_{}_{}_{}".format(
            setting.project_nummer.lower(),
            setting.organisatie,
            onderwerp,
            setting.einddatum,
        )
        workspace_name = "p_{}_{}".format(
            setting.organisatie, setting.product_naam
        )

    else:
        raise ValueError("servernaam fout")

    store_name = "{}_{}".format(
        setting.project_nummer.lower(),
        PG_DATABASE[setting.server_naam]["database"],
    )

    # abstracts and titles
    if setting.product_naam == "klimaatatlas":

        abstract_data = """
        De laag {omschrijving} komt van {bron}. Voor meer informatie over 
        deze laag, ga naar de klimaatatlas www.{bron}.klimaatatlas.net. 
        """.format(
            omschrijving=onderwerp.lower(), bron=setting.organisatie.lower()
        )
        database_name = None
        schema_name = "public"

    elif setting.product_naam == "lizard":
        abstract_data = """
        De laag {omschrijving} komt van {bron}. 
        """.format(
            omschrijving=onderwerp.lower(), bron=setting.organisatie.lower()
        )
        database_name = None
        schema_name = "public"

    elif setting.product_naam == "storymap":
        abstract_data = """ Deze laag is afkomsting van de storymap van
        {bron}.
        """.format(
            omschrijving=onderwerp.lower(), bron=setting.organisatie.lower()
        )
        database_name = None
        schema_name = "public"

    elif setting.product_naam == "catalogus":
        abstract_data = """ 
        De laag {omschrijving} komt van {bron}. Voor meer informatie over 
        deze laag, ga naar de klimaatatlas www.{bron}.klimaatatlas.net. 
        """.format(
            omschrijving=onderwerp.lower(), bron=setting.organisatie.lower()
        )
        database_name = None
        schema_name = "public"

    elif setting.product_naam == "flooding":
        """flooding has no restrictions"""

        abstract_data = ""
        layer_name = onderwerp
        workspace_name = setting.workspace
        schema_name = setting.schema
        database_name = setting.database
        store_name = setting.store

    else:
        raise ValueError("productnaam fout")

    # title
    title_data = layer_name

    # slug
    slug = ":".join([workspace_name, layer_name][:50])

    # wms
    wms_url = REST[setting.server_naam].replace(
        "rest", "{}/wms".format(workspace_name)
    )

    # lizard wms acces
    access = 0

    # Source inputs
    if setting.use_postgis and not os.path.isfile(in_path):

        setting.set_values(in_path)
        setting.in_datasource = {
            "host": setting.host,
            "port": setting.port,
            "database": setting.database,
            "username": setting.username,
            "password": setting.password,
        }
        setting.in_layer = in_path
        setting.skip = setting.skip

    elif setting.use_directory and os.path.isfile(in_path):

        setting.in_datasource = in_path
        setting.in_layer = None
        setting.in_sld_path = in_path.replace(
            os.path.splitext(in_path)[1], ".sld"
        )
        setting.skip = False

        # Extra directory setting
        try:
            setting.set_values(os.path.basename(in_path))
            if not setting.skip:
                print("Found additional directory settings")
                if not setting.abstract == "none":
                    abstract_data = setting.abstract
                if not setting.title == "none":
                    title_data = setting.title
                setting.skip = setting.skip

        except Exception:
            pass

    else:
        print("use either use_postgis or use_directory")

    # Overwrite sld path if standard sld is used
    if setting.use_existing_geoserver_sld:
        existing_sld = setting.geoserver_sld
        setting.existing_sld = existing_sld

    # Set metadata
    metadata = {
        "pg_layer": layer_name,
        "gs_workspace": workspace_name,
        "gs_store": store_name,
        "gs_layer": layer_name,
        "uploader": setting.eigen_naam.lower(),
        "projectnummer": setting.project_nummer.lower(),
        "einddatum": setting.einddatum,
    }

    # Add wms layers
    if setting.wms_layer_only or not setting.skip_lizard_wms_layer:

        setting.set_values("lizard_wmslayers")
        setting.wmslayer = wmslayers()

        if setting.atlasjson2wms:
            json_path = in_path.replace(os.path.splitext(in_path)[1], ".json")
            atlas_dict = json.load(open(json_path))["atlas"]

            setting.wmslayer.atlas2wms(
                atlas_dict,
                setting.organisation_uuid,
                setting.dataset,
                setting.eigen_naam,
                setting.organisatie,
                setting.product_naam,
            )

            setting.slug = atlas_dict["slug"]
            wms_url = atlas_dict["url"].replace(
                atlas_dict["workspace"] + "/wms", "/rest/"
            )
            setting.wmsserver = wms_url
            title_data = atlas_dict["name"]

        else:

            setting.wmslayer.configuration = {
                "name": title_data,
                "description": abstract_data,
                "slug": slug,
                "tiled": True,
                "wms_url": wms_url,
                "access_modifier": access,
                "supplier": setting.eigen_naam,
                "options": {"transparent": "true"},
                "shared_with": [],
                "datasets": [setting.dataset],
                "organisation": setting.organisation_uuid,
                "download_url": setting.wmslayer.get_download_url(
                    wms_url, slug
                ),
                "legend_url": setting.wmslayer.get_legend_url(wms_url, slug),
                "get_feature_info_url": wms_url,
                "get_feature_info": True,
            }

    # Overwrite all
    if setting.overwrite_all:
        setting.overwrite_postgres = True
        setting.overwrite_abstract = True
        setting.overwrite_feature = True
        setting.overwrite_sld = True
        setting.overwrite_title = True

    if setting.wms_layer_only:
        setting.skip_mask = True
        setting.skip_correction = True
        setting.skip_sld_check = True
        setting.skip_pg_upload = True
        setting.skip_gs_upload = True
        setting.skip_lizard_wms_layer = False

    # Outputs geoserver
    setting.slug = slug
    setting.wms_url = wms_url
    setting.workspace_name = workspace_name
    setting.store_name = store_name
    setting.layer_name = layer_name
    setting.abstract_data = abstract_data
    setting.subject = onderwerp
    setting.title_data = title_data

    # Outputs postgres server
    setting.database_name = database_name
    setting.schema_name = schema_name
    setting.metadata = metadata
    setting.set_metadata = False

    return setting


def batch_upload(inifile):
    """ Returns batch upload shapes for one geoserver """
    setting = settings_object(inifile)

    # set logging
    set_log_config(setting.ini_location)
    sys.stdout = logger(setting.ini_location)

    # get vectors
    if setting.use_directory:
        setting.set_directory()
        in_paths, subjects = get_paths_and_subjects(setting, "directory")

    elif setting.use_postgis:
        setting.set_postgis()
        in_paths, subjects = get_paths_and_subjects(setting, "postgis")

    elif setting.use_directory and setting.use_postgis:
        in_paths, subjects = get_paths_and_subjects(setting, "directory")
        pg_in_paths, pg_subjects = get_paths_and_subjects(setting, "postgis")

        in_paths = in_paths + pg_in_paths
        subjects = subjects + pg_subjects

    else:
        print("use either use_postgis or use_batch")

    print_list(subjects, "Subjects")
    print_list(in_paths, "Paths")

    failures = {}
    succes = {}
    for count, (in_path, subject) in enumerate(zip(in_paths, subjects)):

        setting = add_output_settings(setting, subject, in_path)

        if not setting.skip:
            log_time("info", percentage(count, len(in_paths)), subject, "l")
            setting.server = wrap_geoserver(setting.server_naam)
            print_dictionary(setting.__dict__, "Layer settings")

            pg_details = PG_DATABASE[setting.server_naam]
            _clear_connections_database(pg_details)

            try:
                succes[setting.subject] = upload(setting)

            except Exception as e:
                print(e)
                failures[setting.subject] = e

            finally:
                _clear_connections_database(pg_details)

            log_time("info", "sleeping to decrease load on server....")
            sleep(2)
        else:
            log_time("info", "Skipping", subject, "l")

    print_dictionary(succes, "Succes")
    print_dictionary(failures, "Failures")


def upload(setting):
    log_time("info", setting.layer_name, "0. starting.....")

    if isinstance(setting.in_datasource, dict):
        _clear_connections_database(setting.in_datasource)

    if not (setting.skip_gs_upload and setting.skip_pg_upload):
        vector = wrap_shape(setting.in_datasource, setting.in_layer)

    if not setting.skip_correction:
        log_time("info", setting.layer_name, "1. vector corrections")
        vector.correct(
            vector.layer,
            setting.layer_name,
            setting.epsg,
            driver="ESRI Shapefile",
        )
        setting.layer_name = vector.layer_name

    if not setting.skip_mask:
        log_time("info", setting.layer_name, "1.2 vector corrections - mask")
        vector_geom = vector_to_geom(setting.mask_path, setting.epsg)
        vector.clip(vector.layer, vector_geom)

    if (not setting.skip_mask) or (not setting.skip_correction):
        if vector.ds[0].GetFeatureCount() == 0:
            log_time("error", setting.layer_name, "vector feature count is 0")
        if vector.ds == None:
            log_time("error", setting.layer_name, "Datasource is none")
        if vector.ds[0][0] == None:
            log_time("error", setting.layer_name, "Feature is none")

    if not setting.skip_delete_excess_field_names:
        vector = wrap_shape(vector.ds)
        field_names = vector.get_all_field_names()
        field_names = [f.lower() for f in field_names]

        sld = wrap_sld(setting.in_sld_path, _type="path")
        sld.lower_all_property_names()
        sld_fields = sld.get_all_property_names()
        for field_name in field_names:
            if field_name not in sld_fields:
                vector.delete_field(field_name)
                continue
            else:
                log_time("info", f"Keeping '{field_name}' field in vector")

    if not setting.skip_pg_upload:
        log_time("info", setting.layer_name, "2. Upload shape to pg database.")

        pg_details = PG_DATABASE[setting.server_naam]
        _clear_connections_database(pg_details)

        if setting.database_name is not None:
            pg_details["database"] = setting.database_name

        pg_database = wrap_shape(pg_details)
        # set metadata
        if not setting.product_naam == "flooding" and setting.set_metadata:
            add_metadata_pgdatabase(setting, pg_database)

        schema_layers = [layer.split(".")[-1] for layer in pg_database.layers]
        pg_layer_present = setting.layer_name in schema_layers

        if not pg_layer_present or setting.overwrite_postgres:
            copy2pg_database(
                pg_database.ds,
                vector.ds,
                vector.layer,
                setting.layer_name,
                setting.schema_name,
            )

        else:
            log_time("info", setting.layer_name, "Layer already in database.")

        pg_database.get_layer(setting.layer_name.lower())
        pg_database.lower_all_field_names()

    if not setting.skip_gs_upload:
        log_time("info", setting.layer_name, "3. Create workspace.")
        server = setting.server
        server.create_workspace(setting.workspace_name)

        log_time("info", setting.layer_name, "4. Create store.")
        pg_details = PG_DATABASE[setting.server_naam]
        server.create_postgis_datastore(
            setting.store_name, setting.workspace_name, pg_details
        )

        log_time("info", setting.layer_name, "5. Publish featuretype.")
        server.publish_layer(
            setting.layer_name,
            setting.workspace_name,
            setting.overwrite_feature,
            setting.epsg,
            reload=True,
        )

        if setting.use_existing_geoserver_sld:
            log_time("info", setting.layer_name, "6-9. Setting existing sld.")
            server.set_sld_for_layer(
                workspace_name=None,
                style_name=setting.existing_sld,
                use_custom=True,
            )
        else:
            log_time(
                "info", setting.layer_name, "6. Load Style Layer Descriptor."
            )

            sld = wrap_sld(setting.in_sld_path, _type="path")

            if not setting.skip_sld_check:
                log_time("info", setting.layer_name, "7. Check sld.")

                # lower all and cut field names to esri shape standards
                sld.lower_all_property_names()
                sld.cut_len_all_property_names(_len=10)

            log_time("info", setting.layer_name, "8. Upload sld.")
            style_name = setting.layer_name + "_style"
            server.upload_sld(
                style_name,
                setting.workspace_name,
                sld.get_xml(),
                setting.overwrite_sld,
            )

            log_time("info", "9. Connect sld to layer.")
            server.set_sld_for_layer()

        log_time("info", setting.layer_name, "10. Add to abstract.")
        if setting.overwrite_abstract:
            server.write_abstract(setting.abstract_data)

        log_time("info", setting.layer_name, "11. Add to title.")
        if setting.overwrite_title:
            server.write_title(setting.title_data)

    if not setting.skip_lizard_wms_layer:
        log_time("info", setting.layer_name, "12. Add wms layer.")
        if not setting.skip_gs_upload:
            gs_wms_server = setting.server
            gs_wms_server.get_layer(setting.slug)
            setting.wmslayer.configuration["wms_url"] = setting.wms_url
            download_url = setting.wmslayer.get_download_url(
                setting.wms_url, setting.slug
            )
            setting.wmslayer.configuration["download_url"] = download_url
            setting.wmslayer.configuration["slug"] = setting.slug

        else:
            gs_wms_server = wrap_geoserver(setting.wmsserver)
            gs_wms_server.get_layer(setting.wmsslug)

        latlon_bbox = gs_wms_server.layer_latlon_bbox
        setting.wmslayer.configuration["spatial_bounds"] = {
            "south": latlon_bbox[2],
            "west": latlon_bbox[0],
            "north": latlon_bbox[3],
            "east": latlon_bbox[1],
        }

        setting.wmslayer.create(setting.wmslayer.configuration, overwrite=True)

    log_time("info", setting.layer_name, "13. Returning wms, slug")
    return setting.wms_url, setting.slug


if __name__ == "__main__":
    batch_upload(**vars(get_parser().parse_args()))
