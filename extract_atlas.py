# -*- coding: utf-8 -*-
"""
Created on Tue Feb  4 13:40:01 2020

@author: chris.kerklaan
"""

import os
import sys

# relevant paths
# TOOLS = "C:/Users/chris.kerklaan/tools"

# if TOOLS not in sys.path:
#    sys.path.append(TOOLS)

# Third-party imports
import ogr
import gdal
import logging
import json
from glob import glob
from tqdm import tqdm
from itertools import chain
from configparser import RawConfigParser
import argparse

# Local imports
from nens_gs_uploader.postgis import SERVERS
from nens_gs_uploader.postgis import connect2pg_database
from nens_gs_uploader.wrap import wrap_geoserver

from nens_gs_uploader.vector import wrap_shape
from nens_gs_uploader.sld import wrap_sld

from nens_gs_uploader.localsecret.localsecret import (
    production_klimaatatlas_v1 as pg_atlas_v1,
    production_klimaatatlas as pg_atlas_v2,
    project_klimaatatlas as pg_atlas_project,
    project_lizard as pg_lizard,
)

from atlas2catalogue.klimaatatlas import wrap_atlas

from nens_raster_uploader.rasterstore import rasterstore
from nens_raster_uploader.geoblocks import (
    clip_waterschappen,
    clip_gemeentes,
    clip_provincies,
)

# Driver
OGR_SHAPE_DRIVER = ogr.GetDriverByName("ESRI Shapefile")
OGR_GPKG_DRIVER = ogr.GetDriverByName("GPKG")

# GLOBALS
POLYGON = "POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"
INSTELLINGEN_PATH = "C:/Users/chris.kerklaan/tools/atlas2catalogue/instellingen"


class MissingSLD(Exception):
    """ Missing an sld"""

    pass


class FoundCoverageStore(Exception):
    pass


class VectorNotFound(Exception):
    pass


class ObservationTypeNotInStore(Exception):
    pass


class StoreNotFound(Exception):
    pass


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "atlas_name", metavar="atlas_name", help="Extract data for atlas."
    )
    parser.add_argument(
        "wd", metavar="working_directory", help="Working directory for data."
    )
    parser.add_argument(
        "--meta_only",
        default=False,
        help="download json only",
        dest="meta_only",
        action="store_true",
    )

    return parser


class settings_object(object):
    """Reads settings from inifile settings from command line tool"""

    def __init__(self, ini_file=None, postgis=True, folder=True):
        if ini_file is not None:
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
        # self.set_values("input_directory")
        self.set_values("tool")

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


def set_log_config(location, name="log"):
    path = os.path.join(location, name)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=path + ".log",
        level=logging.DEBUG,
    )
    gdal.SetConfigOption("CPL_LOG_ERRORS", path + "_gdal_err.log")
    gdal.SetConfigOption("CPL_LOG", path + "_gdal.log")


def mk_dir(path=os.getcwd(), folder_name="temp"):
    tempfolder = os.path.join(path, folder_name)
    if not os.path.exists(tempfolder):
        os.mkdir(tempfolder)
    return tempfolder


def get_rasters_and_vectors(atlas_name):
    atlas = wrap_atlas(atlas_name)
    data = {"vector": [], "raster": [], "other": []}

    for layer in atlas.get_layer_list(atlas_name):
        if ":" in layer["layerName"]:
            layer["layername"] = layer["layerName"].split(":")[-1]
        else:
            layer["layername"] = layer["layerName"]

        layer["slug"] = layer["layerName"]

        servers = [key for key, link in SERVERS.items() if link in layer["url"]]
        if len(servers) > 0:
            url_split = layer["url"].split("/")
            layer["workspace"] = url_split[-2]
            layer["geoserver"] = servers[0]
            data["vector"].append(layer)

        elif "https://demo.lizard.net/" in layer["url"]:
            data["raster"].append(layer)

        else:
            data["other"].append(layer)

    return data


def unique(data):
    unique_data = {}
    for key, value in data.items():
        unique_data[key] = list({v["layername"]: v for v in value}.values())
    return unique_data


def get_vector_sld(geoserver_data, vector):
    return geoserver_data[vector["workspace"]][vector["layername"]]["style"].sld_body


def get_subject_from_name(name, organisation):
    relevant = []
    for count, part in enumerate(name.split("_")):
        if (count == 0) and (not has_numbers(part)):
            relevant.append(part)
        elif (count > 0) and (organisation not in part):
            relevant.append(part)
        else:
            pass

    return "_".join(relevant)


def has_numbers(string):
    return any(char.isdigit() for char in string)


def vector_in_data_directories(name, subdir):

    # check in subdirs
    locations = [
        pg_atlas_v1["folder"],
        pg_atlas_v2["folder"],
        pg_atlas_project["folder"],
        pg_lizard["folder"],
    ]

    paths_subdir = [
        glob(location + "/{}/*.shp".format(subdir)) for location in locations
    ]
    paths_general = [
        glob(location + "/**/*.shp".format(subdir)) for location in locations
    ]
    paths_cover = [
        glob(location + "/**/*.tif".format(subdir)) for location in locations
    ]

    paths_subdir = list(chain(*paths_subdir))
    for path in paths_subdir:
        path_check = path.split("\\")[-1].split(".shp")[0]
        if name in path_check:
            return path

    print("Path not in subdir, checking general")
    paths_general = list(chain(*paths_general))
    for path in paths_general:
        path_check = path.split("\\")[-1].split(".shp")[0]
        if name in path_check:
            return path

    print("Path not as vector, checking coverage stores")
    paths_cover = list(chain(*paths_cover))
    for path in paths_cover:
        path_check = path.split("\\")[-1].split(".tif")[0]
        if name in path_check:
            raise FoundCoverageStore("It is a coverage store")

    raise VectorNotFound("{} not found in {}".format(name, subdir))


def get_datasource(vector, organisation):
    atlas_v1_ds = wrap_shape(connect2pg_database(pg_atlas_v1))
    atlas_v2_ds = wrap_shape(connect2pg_database(pg_atlas_v2))
    atlas_project_ds = wrap_shape(connect2pg_database(pg_atlas_project))
    lizard_project_ds = wrap_shape(connect2pg_database(pg_lizard))

    # check pg databases
    if vector["layername"] in atlas_v1_ds.layers:
        # print('ds atlas v1')
        return atlas_v1_ds.ds
    elif vector["layername"] in atlas_v2_ds.layers:
        # print('ds atlas v2')
        return atlas_v2_ds.ds
    elif vector["layername"] in atlas_project_ds.layers:
        # print('ds atlas porject')
        return atlas_project_ds.ds
    elif vector["layername"] in lizard_project_ds.layers:
        # print('ds lizard project')
        return lizard_project_ds.ds
    else:
        return ogr.Open(vector_in_data_directories(vector["layername"], organisation))

    return 0


def write_vector(layer, layer_name, output_file):
    ds = OGR_GPKG_DRIVER.CreateDataSource(output_file)
    out_layer = ds.CopyLayer(layer, layer_name, ["OVERWRITE=YES"])
    out_layer = None


def delete_excess_raster_info(configuration):
    # delete EXCESS
    del configuration["spatial_bounds"]
    del configuration["last_modified"]
    del configuration["uuid"]
    del configuration["projection"]
    del configuration["origin_x"]
    del configuration["origin_y"]
    del configuration["writable"]
    del configuration["wms_info"]
    del configuration["pixelsize_x"]
    del configuration["pixelsize_y"]
    del configuration["rescalable"]
    del configuration["interval"]
    del configuration["temporal"]
    del configuration["url"]
    del configuration["shared_with"]
    del configuration["datasets"]
    return configuration


def strip_information(information):
    characters = [
        "<p>",
        "</p>",
        "<strong>",
        "</strong>",
        "<br>",
        "<\br?",
        "\n",
        "<em>",
        "<a>",
        "</a>",
        "<em>",
        "</em>",
        "<h5>",
        "</h5>",
        "</ul>",
        "<ul>",
        "<li>",
        "</li>",
        "</ul>",
        "<ul>",
        "<h4>",
        "</h4>",
    ]

    for character in characters:
        information = information.replace(character, "")
    return information


def geoblock_clip(geoblock, clip_list, area="gemeentes"):
    input_block = geoblock["name"]
    graph = geoblock["graph"]
    if input_block == "endpoint":
        input_block = "tussen_resultaat"
        graph[input_block] = graph["endpoint"]
        del graph["endpoint"]

    if area == "gemeentes":
        block_clip = clip_gemeentes(input_block, clip_list)
    elif area == "waterschappen":
        block_clip = clip_waterschappen(input_block, clip_list)
    else:
        block_clip = clip_provincies(input_block, clip_list)

    block_clip = clip_gemeentes(input_block, clip_list)

    for key, value in graph.items():
        block_clip[key] = value

    return block_clip


def set_geoserver_connections(vectors):
    geoservers = []
    for vector in vectors:
        geoservers.append(vector["geoserver"])

    gs_dict = {}
    for geoserver in list(set(geoservers)):
        gs_dict[geoserver] = wrap_geoserver(geoserver, easy=True)

    return gs_dict


def get_uuid_by_organisation(rasters, organisation="Nelen & Schuurmans"):
    store = rasterstore()
    uuid = store.get_organisation_uuid(organisation)["uuid"]

    page = 1
    pages = True
    page_size = 1000

    while pages:
        print(
            "Searching page {}, {} pages for organisation {}".format(
                str(page), str(page_size), organisation
            )
        )

        results = store.organisation_search(page, uuid, page_size=page_size)

        if results is not None:
            page = page + 1
            pages = True

        else:
            pages = False
            results = []

        for raster in rasters:
            result = store.match_results_to_slug(results, raster["layerName"])
            if result is not None:
                print("Adding uuid")
                raster["ori_uuid"] = result

    return rasters


def get_uuid_by_organisations(rasters, organisations):

    for organisation in organisations:
        rasters = get_uuid_by_organisation(rasters, organisation)

    uuid_count = 0
    for raster in rasters:
        if "ori_uuid" in list(raster.keys()):
            uuid_count = uuid_count + 1
    perc = uuid_count / len(rasters)
    print("Percentage uuid complete:", perc, "%")
    return rasters


def extract_vectors(vectors, temp_dir, organisation, meta_only=True):

    extract_data_failures = []
    extract_data_succes = []

    print("Set geoserver connections")
    gs_dict = set_geoserver_connections(vectors)

    print("Extracting vector data")

    for vector in tqdm(vectors):
        try:
            print("Processing vector:", vector["name"])
            json_dict = {}

            subject = get_subject_from_name(vector["layername"], vector["workspace"])
            meta_path = os.path.join(temp_dir, subject + ".json")
            gpkg_path = os.path.join(temp_dir, subject + ".gpkg")

            if os.path.exists(meta_path):
                print("Meta file exists, skipping", subject)
                continue

            if meta_only:
                with open(meta_path, "w") as outfile:
                    json.dump(vector, outfile)
                continue

            vector_ds = get_datasource(vector, organisation)
            vector_layer = vector_ds.GetLayerByName(vector["layername"])

            write_vector(vector_layer, vector["layername"], gpkg_path)

            # retrieve sld
            gs_dict[vector["geoserver"]].get_layer(vector["slug"])
            sld_body = gs_dict[vector["geoserver"]].sld_body
            vector_sld = wrap_sld(sld_body, "body")

            # write vector and sld to temporary folder
            vector_sld.write_xml(os.path.join(temp_dir, subject + ".sld"))

        except MissingSLD as e:
            vector[
                "extract_error"
            ] = "missing sld body layer not in geoserver , {}".format(e)
            extract_data_failures.append(vector)
            vector["temp_path"] = None

        except VectorNotFound as e:
            vector["extract_error"] = "vector not in directory or postgis {}".format(e)
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        except FoundCoverageStore as e:
            vector["extract_error"] = "Found coverage store instead of vector{}".format(
                e
            )
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        except AttributeError as e:
            vector["extract_error"] = "Vector in postgres db but not in gs{}".format(e)
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        else:
            vector["temp_path"] = gpkg_path
            vector["subject"] = subject
            extract_data_succes.append(vector)

        finally:
            json_dict["atlas"] = vector
            with open(meta_path, "w") as outfile:
                json.dump(json_dict, outfile)

    return extract_data_succes, extract_data_failures


def extract_rasters(rasters, atlas_name, dataset, temp_dir, use_nens=False):

    raster_failures = []
    raster_succes = []

    # Start raster changes
    for raster in rasters:
        json_dict = {}
        subject = "_".join(raster["name"].lower().split(" "))

        print(subject)
        meta_path = os.path.join(temp_dir, subject + ".json")

        try:
            print("Processing raster:", raster["name"])
            store = rasterstore()

            # get store configuration
            search_terms = (
                [raster["name"]]
                + raster["name"].split(" ")
                + raster["name"].split("-")
                + [raster["layername"]]
                + raster["layername"].split("_")
            )

            #            if raster['uuid'] is None:
            #                store_configuration =  store.get_store(search_terms , raster['slug'])[0]
            #            else:
            store_configuration = store.get_store(
                search_terms, raster["slug"], method="search", uuid=None
            )

            # copy rasterstore
            configuration_new = store_configuration[0]
            if configuration_new is None:
                raise StoreNotFound("Did not find rasterstore")

        except StoreNotFound as e:
            print(e)
            json_dict["extract_error"] = "Rasterstore not Found"
            raster_failures.append(e)
        else:
            raster_succes.append(raster)

        finally:
            json_dict["rasterstore"] = configuration_new
            json_dict["atlas"] = raster
            with open(meta_path, "w") as outfile:
                json.dump(json_dict, outfile)

    print("completed")
    print("final failures", len(raster_failures))
    return raster_succes, raster_failures


def extract_atlas(atlas_name, wd, meta_only):
    """ Returns batch upload shapes for one geoserver """

    os.chdir(wd)

    vector_dir = mk_dir(os.getcwd(), folder_name="extract_vector")
    raster_dir = mk_dir(os.getcwd(), folder_name="extract_raster")

    # step 1 get a look inside the atlas
    data = get_rasters_and_vectors(atlas_name)
    unique_data = unique(data)
    vectors = unique_data["vector"]
    rasters = unique_data["raster"]
    other_data = unique_data["other"]

    print("Raster directory:", raster_dir)
    print("Vector directory:", vector_dir)
    print("Amount of vectors: {}".format(len(vectors)))
    print("Amount of rasters: {}".format(len(rasters)))
    print("Amount of other data: {}".format(len(other_data)))

    # extract vector data from their respective sources
    extract_succes, extract_failure = extract_vectors(
        vectors, vector_dir, atlas_name, meta_only=meta_only
    )

    raster_succes, raster_failures = extract_rasters(
        rasters, atlas_name, dataset, raster_dir, use_nens=False
    )


if __name__ == "__main__":
    wd = "C:/Users/chris.kerklaan/Documents/Projecten/westland"
    atlas_name = "westland"
    meta_only = False
    dataset = "test_klimaatatlas"
    extract_atlas(**vars(get_parser().parse_args()))
