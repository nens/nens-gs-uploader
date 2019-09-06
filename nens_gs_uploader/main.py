# -*- coding: utf-8 -*-
"""
Created on Wed Jul 24 15:39:13 2019

@author: chris.kerklaan - N&S
TODOs:
    1. Op basis van ini.file ipv command line tool
    2. Code review
    3. Black voor formatten van scripts
    

"""
# system imports
import os
import logging
from time import sleep
from configparser import RawConfigParser

# Third-party imports
import ogr
import gdal
import argparse

# Local imports
from postgis import (
    SERVERS,
    PG_DATABASE,
    copy2pg_database,
    add_metadata_pgdatabase,
)

from wrap import wrap_geoserver
from vector import wrap_shape
from sld import wrap_sld
from sld import replace_sld_field_based_on_shape
from upload_ready import correct
from project import log_time, percentage

# Logging directory
loc = os.path.dirname(os.path.abspath(__file__))

# Globals
DRIVER_OGR_SHP = ogr.GetDriverByName("ESRI Shapefile")
DRIVER_OGR_MEM = ogr.GetDriverByName("Memory")

# Exceptions
ogr.UseExceptions()
gdal.UseExceptions()

# GDAL configuration options
gdal.SetConfigOption("CPL_DEBUG", "ON")
gdal.SetConfigOption("CPL_LOG_ERRORS", os.path.join(loc, "log/gdal_err.log"))
gdal.SetConfigOption("CPL_LOG", os.path.join(loc, "log/gdal.log"))
gdal.SetConfigOption("CPL_CURL_VERBOSE", "ON")
gdal.SetConfigOption("PG_USE_COPY", "ON")

# Logging configuration options
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=os.path.join(loc, "log/upload.log"),
    level=logging.DEBUG,
)


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inifile", metavar="INIFILE", help="Settings voor inifile"
    )
    parser.add_argument(
        "bo_nummer",
        metavar="BO_NUMMER",
        help="B&O nummer van het betreffende project.",
    )
    parser.add_argument(
        "organisatie",
        metavar="ORGANISATIE",
        help="Opdrachtgever van het betreffende project (hhnk, vechtstromen).",
    )
    parser.add_argument(
        "productnaam",
        metavar="PRODUCTNAAM",
        help='Het product, bijvoorbeeld: "klimaatatlas" of "dashboard".',
    )

    parser.add_argument(
        "server_name",
        metavar="SERVER",
        help='Bijvoorbeeld "PRODUCTIE_KLIMAATATLAS" of "PROJECTEN_LIZARD."\n'
        "Let op: moet met hoofdletters.",
    )
    parser.add_argument(
        "eigen_naam",
        metavar="NAAM_VAN_DE_UPLOADER",
        help="Naam van de uploader van de shapes.",
    )
    parser.add_argument(
        "projectnummer",
        metavar="PROJECTNUMMER",
        help="projectnummer van het betreffende project.",
    )
    parser.add_argument(
        "directory",
        metavar="DIRECTORY",
        help="Pad naar de dirctory waar zowel alle shapefiles als slds staan.",
    )
    parser.add_argument(
        "-c", "--check_sld", default=True, help="Check je sld op fouten."
    )
    parser.add_argument(
        "-o",
        "--overwrite_all",
        default=False,
        help="Overschrijf alle databronnen.",
    )
    parser.add_argument(
        "-op",
        "--overwrite_postgres",
        default=False,
        help="Overwrite een al bestaande laag in de postgres database.",
    )
    parser.add_argument(
        "-oa",
        "--overwrite_abstract",
        default=False,
        help="Overwrite de abstract binnen de GeoServer.",
    )
    parser.add_argument(
        "-of",
        "--overwrite_feature",
        default=False,
        help="Overwrite een al bestaande shapelaag in de GeoServer.",
    )
    parser.add_argument(
        "-os",
        "--overwrite_sld",
        default=False,
        help="Overwrite een al bestaande sld in de GeoServer.",
    )
    return parser


def print_list(_list, subject):
    print("\n {}:".format(subject))
    for path in _list:
        print("\t{}".format(path))


def print_dictionary(_dict, subject):
    print("\n {}:".format(subject))
    for key, value in _dict.items():
        print("\t{}:\t\t{}".format(key, value))


def get_subject_from_path(path):
    return path.split("\\")[-1].split(".shp")[0]


class settings_object(object):
    """Contains the settings from command line tool"""

    def __init__(self, ini_file=None):
        if ini_file is not None:
            config = RawConfigParser()
            config.read(ini_file)
            self.ini = ini_file

            for section in config.sections():
                for key, value in config.items(section):
                    setattr(self, key, value)

    def add(self, key, value):
        setattr(self, key, value)


class settingsObject(object):
    """Contains the settings from the ini file"""

    def __init__(self, inifile):
        config = RawConfigParser()
        config.read(inifile)

        # inifile
        self.ini = inifile

        for section in config.sections():
            for key, value in config.items(section):
                setattr(self, key, value)


def package_input(
    bo_nummer,
    organisatie,
    productnaam,
    eigen_naam,
    projectnummer,
    directory,
    server_name,
    check_sld,
    overwrite_all,
    overwrite_postgres,
    overwrite_abstract,
    overwrite_feature,
    overwrite_sld,
):
    """ Returns all settings needed for upload in a dictionary """
    setting = settings_object()

    inputs = {
        # input data
        "bo_nummer": bo_nummer,
        "organisatie": organisatie,
        "product_naam": productnaam,
        "eigen_naam": eigen_naam,
        "projectnummer": projectnummer,
        "directory": directory,
        # output data
        "server_name": server_name,
        # sld
        "check_sld": check_sld,
        # overwrite
        "overwrite_postgres": overwrite_postgres,
        "overwrite_feature": overwrite_feature,
        "overwrite_sld": overwrite_sld,
        "overwrite_abstract": overwrite_abstract,
        "overwrite_all": overwrite_all,
    }

    for key, value in inputs.items():
        setting.add(key, value)

    return setting


def add_output_settings(setting, onderwerp, shape_path):
    """ Returns geoserver settings in an organized manner"""

    workspace_name = setting.organisatie + "_" + setting.product_naam
    store_name = PG_DATABASE[setting.server_name]["database"]
    layer_name = "{}_{}_{}".format(
        setting.bo_nummer, setting.organisatie, onderwerp
    )

    abstract_data = """
    De laag {omschrijving} komt van {bron}. Voor meer informatie over 
    deze laag, ga naar de klimaatatlas www.{bron}.klimaatatlas.net. 
    """.format(
        omschrijving=onderwerp.lower(), bron=setting.organisatie.lower()
    )

    metadata = {
        "pg_layer": layer_name,
        "gs_workspace": workspace_name,
        "gs_store": store_name,
        "gs_layer": layer_name,
        "uploader": setting.eigen_naam.lower(),
        "projectnummer": setting.projectnummer.lower(),
    }
    # Overwrite all
    if setting.overwrite_all:
        setting.overwrite_postgres = True
        setting.overwrite_abstract = True
        setting.overwrite_feature = True
        setting.overwrite_sld = True

    # Inputs
    setting.add("in_datasource", shape_path)
    setting.add("in_sld_path", shape_path.replace(".shp", ".sld"))

    # Outputs
    setting.add("workspace_name", workspace_name)
    setting.add("store_name", store_name)
    setting.add("layer_name", layer_name)
    setting.add("abstract_data", abstract_data)
    setting.add("metadata", metadata)

    return setting


def batch_upload(setting):
    """ Returns batch upload shapes for one geoserver """

    shape_paths = []
    for dirpath, dirname, filename in os.walk(setting.directory):
        for file in filename:
            if file.endswith(".shp"):
                shape_paths.append(os.path.join(dirpath, file))

    print_list(shape_paths, "Paths")
    print_dictionary(setting.__dict__, "Settings")

    failures = {}
    succes = {}
    for count, shape_path in enumerate(shape_paths):

        # prints and subject
        subject = get_subject_from_path(shape_path)
        log_time("info", percentage(count, len(shape_paths)), subject, "l")

        # set last settings
        setting.add("server", wrap_geoserver(setting.server_name))
        setting = add_output_settings(setting, subject, shape_path)

        try:
            succes[subject] = upload(setting)

        except Exception as e:
            print(e)
            failures[subject] = e

        log_time("info", "sleeping to decrease load on server....")
        sleep(30)

    print_dictionary(succes, "Succes")
    print_dictionary(failures, "Failures")


def upload(setting):
    log_time("info", setting.layer_name, "0. starting.....")
    shape = wrap_shape(setting.in_datasource)

    log_time("info", setting.layer_name, "1. vector corrections")
    datasource, layer_name = correct(shape.layer, setting.layer_name)
    shape = wrap_shape(datasource)
    setting.layer_name = layer_name

    if shape.layer.GetFeatureCount() is 0:
        log_time("error", setting.layer_name, "Shape feature count is 0")

    log_time("info", setting.layer_name, "2. Upload shape to pg database.")
    pg_details = PG_DATABASE[setting.server_name]
    pg_database = wrap_shape(pg_details)

    # set metadata
    add_metadata_pgdatabase(setting, pg_database)

    pg_layer_present = setting.layer_name in pg_database.layers
    if not pg_layer_present or setting.overwrite_postgres:
        copy2pg_database(pg_database, shape.layer, setting.layer_name)

    else:
        log_time("info", setting.layer_name, "Layer already in database.")

    log_time("info", setting.server_name, "Loading...")
    server = setting.server

    log_time("info", setting.layer_name, "3. Create workspace.")
    server.create_workspace(setting.workspace_name)

    log_time("info", setting.layer_name, "4. Create store.")
    server.create_postgis_datastore(
        setting.store_name, setting.workspace_name, pg_details
    )

    log_time("info", setting.layer_name, "5. Publish featuretype.")
    server.publish_layer(setting.layer_name, setting.overwrite_feature)

    log_time("info", setting.layer_name, "6. Load Style Layer Descriptor.")
    sld = wrap_sld(setting.in_sld_path, _type="path")

    log_time("info", setting.layer_name, "7. Possibly check sld.")
    pg_database.get_layer(setting.layer_name)

    # lower all field names if necessary
    pg_database.lower_all_field_names
    sld.lower_all_property_names()

    if setting.check_sld:
        if sld._type() is "category":
            for sld_field_name in sld.get_all_property_names():
                if not sld_field_name in pg_database.get_all_field_names():
                    replace_sld_field_based_on_shape(
                        pg_database, sld, sld_field_name
                    )

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

    log_time("info", setting.layer_name, "11. Returning wms, slug")
    wms = SERVERS[setting.server_name].replace("rest", "wms")
    slug = "{}:{}".format(setting.workspace_name, setting.layer_name)

    return wms, slug


if __name__ == "__main__":
    batch_upload((package_input(**vars(get_parser().parse_args()))))

#    bo_nummer="1833"
#    organisatie="hlt"
#    productnaam="klimaatatlas"
#    eigen_naam="chris.kerklaan"
#    projectnummer= "t0270"
#
#    directory = "C:/Users/chris.kerklaan/Documents/Projecten/hltsamen/vector"
#    server_name = "PRODUCTIE_KLIMAATATLAS"
#    check_sld=False
#    overwrite_postgres = False
#    overwrite_abstract = False
#    overwrite_feature = False
#    overwrite_sld = False
#    overwrite_all = True
#
#    setting = package_input(bo_nummer, organisatie, productnaam, eigen_naam,
#                           projectnummer, directory, server_name,
#                           check_sld, overwrite_all, overwrite_postgres,
#                           overwrite_abstract, overwrite_feature, overwrite_sld)
#    batch_upload(setting)

#
#
# bbox = server.catalog.get_layer(setting.layer_name).resource.native_bbox
# xmin, ymin, ymax, xmax, epsg = bbox

#    preview = """
#    {wms}{workspace_name}/wms?service=WMS&version=1.1.0&request=GetMap
#    &layers={workspace_name}:{layer_name}&bbox={xmin},{ymax},{ymin},{xmax}
#    &width=611&height=768&srs={epsg}&format=application/openlayers
#    """.format(
#                wms             = wms.split("wms/")[0],
#                workspace_name  = setting.workspace_name,
#                layer_name      = setting.layer_name,
#                xmin            = xmin,
#                xmax            = xmax,
#                ymin            = ymin,
#                ymax            = ymax,
#                epsg            = epsg
#                )
