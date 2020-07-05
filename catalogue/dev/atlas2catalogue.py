# -*- coding: utf-8 -*-
"""
Created on Fri Jul 26 09:05:11 2019

@author: chris.kerklaan


TODO:
    1. Alles voor consultants
    
"""
import os
import sys

# relevant paths
TOOLS = "C:/Users/chris.kerklaan/tools"

if TOOLS not in sys.path:
    sys.path.append(TOOLS)

# Third-party imports
import ogr
import gdal
import logging
import json
import argparse
from glob import glob
from tqdm import tqdm
from shutil import copyfile
from itertools import chain
from configparser import RawConfigParser

# Local imports
from catalogue.wrap import SERVERS
from nens_gs_uploader.postgis import connect2pg_database
from nens_gs_uploader.wrap import wrap_geoserver

from nens_gs_uploader.vector import vector_to_geom, vector_clip
from nens_gs_uploader.vector import wrap_shape
from nens_gs_uploader.upload_ready import correct

from nens_gs_uploader.sld import wrap_sld

from nens_gs_uploader.project import (
    logger,
    log_time,
    percentage,
    print_list,
    print_dictionary,
)

from nens_gs_uploader.localsecret.localsecret import (
    production_klimaatatlas_v1 as pg_atlas_v1,
    production_klimaatatlas as pg_atlas_v2,
    project_klimaatatlas as pg_atlas_project,
    project_lizard as pg_lizard,
)

from atlas2catalogue.klimaatatlas import wrap_atlas
from atlas2catalogue.wmslayers import wmslayers

from nens_raster_uploader.rasterstore import rasterstore
from nens_raster_uploader.geoblocks import (
    clip_waterschappen,
    clip_gemeentes,
    clip_provincies,
)
from nens_raster_uploader.geoblocks import uuid_store

# Driver
OGR_SHAPE_DRIVER = ogr.GetDriverByName("ESRI Shapefile")
OGR_GPKG_DRIVER = ogr.GetDriverByName("GPKG")

# GLOBALS
POLYGON = "POLYGON (({x1} {y1},{x2} {y1},{x2} {y2},{x1} {y2},{x1} {y1}))"
INSTELLINGEN_PATH = (
    "C:/Users/chris.kerklaan/tools/atlas2catalogue/instellingen"
)


class MissingSLD(Exception):
    """ Missing an sld"""

    pass


class FoundCoverageStore(Exception):
    pass


class VectorNotFound(Exception):
    pass


class ObservationTypeNotInStore(Exception):
    pass


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inifile", metavar="INIFILE", help="Settings voor inifile."
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

        servers = [
            key for key, link in SERVERS.items() if link in layer["url"]
        ]
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
    return geoserver_data[vector["workspace"]][vector["layername"]][
        "style"
    ].sld_body


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
        return atlas_v1_ds.datasource
    elif vector["layername"] in atlas_v2_ds.layers:
        # print('ds atlas v2')
        return atlas_v2_ds.datasource
    elif vector["layername"] in atlas_project_ds.layers:
        # print('ds atlas porject')
        return atlas_project_ds.datasource
    elif vector["layername"] in lizard_project_ds.layers:
        # print('ds lizard project')
        return lizard_project_ds.datasource
    else:
        return ogr.Open(
            vector_in_data_directories(vector["layername"], organisation)
        )

    return 0


def write_vector(layer, layer_name, output_file):
    ds = OGR_GPKG_DRIVER.CreateDataSource(output_file)
    out_layer = ds.CopyLayer(layer, layer_name, ["OVERWRITE=YES"])
    out_layer = None


def create_nens_gs_uploader_instellingen(upload_dir, **kwargs):
    settings_location = os.path.join(INSTELLINGEN_PATH, "nens_gs_uploader.ini")
    output_location = os.path.join(upload_dir, "nens_gs_uploader.ini")
    copyfile(settings_location, output_location)

    settings_file = open(output_location, "rt")
    settings = settings_file.read()
    for key, value in kwargs.items():
        settings = settings.replace(key, value)
    settings_file.close()

    new_file = open(output_location, "wt")
    new_file.write(settings)
    new_file.close()


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

    len
    uuid_count = 0
    for raster in rasters:
        if "ori_uuid" in list(raster.keys()):
            uuid_count = uuid_count + 1
    perc = uuid_count / len(rasters)
    print("Percentage uuid complete:", perc, "%")
    return rasters


def extract_vector_data(vectors, temp_dir, organisation, meta_only=True):

    extract_data_failures = []
    extract_data_succes = []

    print("Set geoserver connections")
    gs_dict = set_geoserver_connections(vectors)

    print("Extracting vector data")
    for vector in tqdm(vectors):
        try:
            subject = get_subject_from_name(
                vector["layername"], vector["workspace"]
            )
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
            vector[
                "extract_error"
            ] = "vector not in directory or postgis {}".format(e)
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        except FoundCoverageStore as e:
            vector[
                "extract_error"
            ] = "Found coverage store instead of vector{}".format(e)
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        except AttributeError as e:
            vector[
                "extract_error"
            ] = "Vector in postgres db but not in gs{}".format(e)
            vector["temp_path"] = None
            extract_data_failures.append(vector)

        else:
            vector["temp_path"] = gpkg_path
            vector["subject"] = subject
            extract_data_succes.append(vector)

        finally:
            with open(meta_path, "w") as outfile:
                json.dump(vector, outfile)

    return extract_data_succes, extract_data_failures


def upload_ready(
    temp_dir,
    upload_dir,
    clip_geom,
    organisation,
    bo_nummer,
    epsg,
    dataset,
    meta_only=True,
):

    upload_ready_succes = []
    upload_ready_failures = []

    print("Making it upload ready")
    for meta_path in tqdm(glob(temp_dir + "/*.json")):

        vector_path = meta_path.replace(".json", ".gpkg")
        meta_data = json.load(open(meta_path))
        vector_name = get_subject_from_name(
            os.path.basename(vector_path).split(".")[0], organisation
        )

        vector_length = 62 - len(
            "{}:{}_{}_".format(dataset, bo_nummer, organisation)
        )
        vector_name_new = vector_name[:vector_length]
        meta_data["vector_name"] = vector_name_new
        meta_data["slug_new"] = "{}:{}_{}_{}".format(
            dataset, bo_nummer, organisation, vector_name_new
        )

        if meta_only:
            meta_out = os.path.join(upload_dir, vector_name_new + ".json")
            with open(meta_out, "w") as out_file:
                json.dump(meta_data, out_file)
            continue

        feature_store = True
        sld_store = True

        try:
            if "coverage" in meta_data["extract_error"]:
                feature_store = False
                sld_store = False
            elif "sld" in meta_data["extract_error"]:
                sld_store = False
            else:
                pass

            print("Error, incomplete data", meta_data["extract_error"])

        except Exception:
            pass

        if feature_store:
            vector_ds = ogr.Open(vector_path)
            vector_layer = vector_ds[0]

            corrected_ds, layer_name = correct(vector_layer, epsg=epsg)

            # clip
            clipped_ds = vector_clip(corrected_ds[0], clip_geom)
            clipped_layer = clipped_ds[0]

            if clipped_layer.GetFeatureCount() == 0:
                print("clip fail, feature count is 0")
                raise ValueError("clip fail, feature count is 0")

                match = (
                    clipped_layer.GetFeatureCount()
                    / vector_layer.GetFeatureCount()
                )
                if match < 0.95:
                    raise ValueError("low clip match", match, "%")

            output_file = os.path.join(upload_dir, vector_name_new + ".gpkg")
            write_vector(clipped_layer, vector_name_new, output_file)

        # copy sld

        if sld_store:
            sld_in = os.path.join(temp_dir, meta_path.replace(".json", ".sld"))
            sld_out = os.path.join(upload_dir, vector_name_new + ".sld")
            copyfile(sld_in, sld_out)

        meta_out = os.path.join(upload_dir, vector_name_new + ".json")
        with open(meta_out, "w") as out_file:
            json.dump(meta_data, out_file)

    return upload_ready_succes, upload_ready_failures


def upload_data(
    upload_dir, bo_nummer, organisation, eigen_naam, project_nummer
):
    create_nens_gs_uploader_instellingen(
        upload_dir,
        bo_nummer_replace=bo_nummer,
        organisatie_replace=organisation,
        eigen_naam_replace=eigen_naam,
        projectnummer_replace=project_nummer,
        directory_replace=upload_dir,
    )

    ini_file = os.path.join(upload_dir, "nens_gs_uploader.ini")
    ini_file_title = os.path.join(upload_dir, "nens_gs_uploader_titles.ini")

    config = RawConfigParser()
    config.read(ini_file)

    for vector_path in tqdm(glob(upload_dir + "/*.gpkg")):

        meta_path = vector_path.replace(".gpkg", ".json")
        meta_data = json.load(open(meta_path))

        config.add_section(os.path.basename(vector_path))
        config.set(os.path.basename(vector_path), "title", meta_data["name"])
        config.set(
            os.path.basename(vector_path),
            "abstract",
            strip_information(meta_data["information"]),
        )
        config.set(os.path.basename(vector_path), "skip", "False")

    with open(ini_file_title, "w") as newini:
        config.write(newini)

    os.system(
        "python C:/Users/chris.kerklaan/tools/nens_gs_uploader.py {}".format(
            ini_file_title
        )
    )


def create_wmslayers(upload_dir, organisation, dataset, use_nens=True):

    wmslayer_failures = []
    wmslayer_succes = []
    wmslayer = wmslayers()

    for meta_path in glob(upload_dir + "/*.json"):
        meta_data = json.load(open(meta_path))

        vector_name = meta_data["vector_name"]
        wms_info, result_exists = wmslayer.get_layer(vector_name)

        if result_exists:
            wmslayer.delete(wms_info["uuid"])

        if use_nens:
            organisation_uuid = wmslayer.get_nens_id()
        else:
            organisation_uuid = wmslayer.get_organisation_id(organisation)

        # set description
        try:
            wmslayer_description = strip_information(meta_data["information"])

        except KeyError:
            wmslayer_description = ""

        # set name of layer
        try:
            name = meta_data["name"][:80]

        except KeyError:
            name = vector_name[:80]

        try:
            if "coverage" in meta_data["extract_error"]:
                error = True
            elif "sld" in meta_data["extract_error"]:
                error = True
            else:
                error = False

        except Exception:
            error = False

        if error:
            slug = meta_data["slug"].lower()
            url = meta_data["url"]
        else:
            slug = meta_data["slug_new"].lower()
            url = "https://maps1.klimaatatlas.net/geoserver/{}_klimaatatlas/wms".format(
                organisation
            )

        # download link
        download_url = "{}?&request=GetFeature&typeName={}&OutputFormat=shape-zip".format(
            url.replace("wms", "wfs"), slug
        )

        configuration = {
            "name": name + "_test",
            "description": wmslayer_description,
            "slug": slug + "_test",
            "tiled": True,
            "wms_url": url,
            "access_modifier": 0,
            "supplier": "chris.kerklaan",
            "options": {"transparent": "true"},
            "shared_with": [],
            "datasets": [dataset],
            "organisation": organisation_uuid,
            "download_url": download_url,
        }

        print(configuration["name"], configuration["slug"])
        meta_data["wmslayer"] = wmslayer.create(configuration, overwrite=True)

    #        except Exception as e:
    #            print(e)
    #            wmslayer_failures.append(vector)
    #
    #        else:
    #            wmslayer_succes.append(vector)
    return wmslayer_succes, wmslayer_failures


def atlas2catalogue_rasterstores(
    rasters,
    clip_list,
    bo_nummer,
    organisation,
    dataset,
    use_nens=False,
    overwrite=False,
):

    raster_failures = []
    raster_succes = []

    # Start raster changes
    for raster in rasters:
        print("Processing layer:", raster["name"])

        #        try:
        # raster = rasters[0]
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
            search_terms, raster["slug"], method="uuid", uuid=raster["uuid"]
        )

        # copy rasterstore
        configuration_new = store_configuration[0]
        if configuration_new is None:
            return print("Store not found")

        # add clip top copied rasterstore
        geoblock = uuid_store(raster["uuid"])
        graph = geoblock_clip(geoblock, clip_list)
        configuration_new["source"] = {"graph": graph, "name": "endpoint"}

        # set dataset, does not work yet
        # configuration_new['datasets'] = [dataset]

        # acces modifier
        configuration_new["access_modifier"] = 0

        # name
        configuration_new["name"] = raster["name"]
        # configuration_new['name'] = configuration_new['name'].lower()

        # supplier
        configuration_new["supplier"] = "chris.kerklaan"

        # Description
        configuration_new["description"] = strip_information(
            raster["information"]
        )

        # observation type
        try:
            code = configuration_new["observation_type"]["code"]
        except TypeError:
            code = "Waterdepth"

        configuration_new["observation_type"] = code
        # organisation & slug name

        if use_nens:
            store.organisation_uuid = "61f5a464-c350-44c1-9bc7-d4b42d7f58cb"
        else:
            store.get_organisation_uuid(organisation)

        # slug search name
        slug_name = configuration_new["name"].replace(" ", "-").lower()
        slug_org = organisation
        slug = "{}:{}".format(slug_org, slug_name)

        # format slug to 64 characters
        slug = slug[:64]

        # styles
        configuration_new = delete_excess_raster_info(configuration_new)

        # add search terms
        configuration_new["search_terms"] = search_terms

        # add datasets
        configuration_new["datasets"] = [dataset]

        # add slug for search
        configuration_new["slug"] = slug

        # create stores
        store.create(configuration_new, overwrite=overwrite)

    #        else:
    #            print('Output:', configuration_new['name'])
    #            raster_succes.append(raster)

    print("completed")
    print("final failures", len(raster_failures))
    return raster_succes, raster_failures


def create_catalogue(inifile):
    """ Returns batch upload shapes for one geoserver """
    setting = settings_object(inifile)

    # set logging
    set_log_config(setting.ini_location)
    sys.stdout = logger(setting.ini_location)

    raster_clip_id = [int(setting.raster_clip_id)]

    os.chdir(setting.wd)

    temp_dir = mk_dir(setting.wd)
    upload_dir = mk_dir(setting.wd, folder_name="upload")

    # step 1 get a look inside the atlas
    data = get_rasters_and_vectors(setting.atlas_name)
    unique_data = unique(data)
    vectors = unique_data["vector"]
    rasters = unique_data["raster"]
    other_data = unique_data["other"]

    print("Temporary directory:", temp_dir)
    print("Upload directory:", upload_dir)
    print("Amount of vectors: {}".format(len(vectors)))
    print("Amount of rasters: {}".format(len(rasters)))
    print("Amount of other data: {}".format(len(other_data)))

    # get geoserver_data for looking up vector sld's
    clip_geom = vector_to_geom(setting.area_path, epsg=3857)

    # extract vector data from their respective sources
    extract_succes, extract_failure = extract_vector_data(
        vectors, temp_dir, setting.organisatie, meta_only=setting.meta_only
    )

    # make them upload ready
    ready_succes, ready_failure = upload_ready(
        temp_dir,
        upload_dir,
        clip_geom,
        setting.organisatie,
        setting.bo_nummer,
        epsg=int(setting.epsg),
        dataset=setting.dataset,
        meta_only=setting.meta_only,
    )

    if not setting.meta_only:
        # upload them to the geoserver
        upload_data(
            upload_dir,
            setting.bo_nummer,
            setting.organisatie,
            eigen_naam,
            project_nummer,
        )

    # create wms layers
    wmslayer_succes, wmslayer_failures = create_wmslayers(
        upload_dir, setting.organisatie, setting.dataset, use_nens=True
    )

    # copy rasterstore, add clip and add to dataset
    # cannot find correct stores
    organisations = ["Provincie Zuid-Holland", "Nelen & Schuurmans"]
    rasters = get_uuid_by_organisations(rasters, organisations)

    rasters[0]["uuid"] = "197c72b9-3f64-440c-9025-3883fef94316"
    rasters[1]["uuid"] = "f28bb892-20cb-4a31-90c8-5f6cd715ddbe"
    rasters[2]["uuid"] = "5d3fc11c-5819-419a-85be-a53fa945c926"
    rasters[3]["uuid"] = "9b40ef35-05bd-4473-a8cf-83338bdbb210"
    rasters[4]["uuid"] = "cf09302b-0228-4220-b5a4-b7b5461f7fcf"
    rasters[5]["uuid"] = "0d7fdf72-3f22-40b8-85ab-419acaba446d"
    rasters[6]["uuid"] = "5aad9db6-7b71-49aa-9759-7dad26802c3c"
    rasters[7]["uuid"] = "f50e8ad6-66cf-4247-9188-7cde3c0e976f"
    rasters[7]["slug"] = rasters[7]["slug"].split(",")[1]
    rasters[8]["uuid"] = "1d65a4e1-ac2f-4e66-9e52-1d130d870a34"
    rasters[9]["uuid"] = "9c6f0130-001b-4747-9c9f-2a65b9370b32"

    raster_succes, raster_failures = atlas2catalogue_rasterstores(
        rasters,
        raster_clip_id,
        bo_nummer,
        organisatie,
        dataset,
        overwrite=False,
    )


if __name__ == "__main__":
    create_catalogue(**vars(get_parser().parse_args()))

    # # input arugments
    # atlas_name = "hhnk"
    # area_path = (
    #     "C:/Users/chris.kerklaan/Documents/Projecten/westland/westland.shp"
    # )
    # dataset = "westland_klimaatatlas"
    # raster_clip_id = [40]

    # # project details
    # bo_nummer = "1836"
    # organisatie = "westland"
    # project_nummer = "u0305"
    # eigen_naam = "chris.kerklaan"
    # wd = "C:/Users/chris.kerklaan/Documents/Projecten/westland/"

    # os.chdir(wd)
    # temp_dir = mk_dir()
    # upload_dir = mk_dir(folder_name="upload")

    # # step 1 get a look inside the atlas
    # data = get_rasters_and_vectors(atlas_name)
    # unique_data = unique(data)
    # vectors = unique_data["vector"]
    # rasters = unique_data["raster"]
    # other_data = unique_data["other"]

    # print("Temporary directory:", temp_dir)
    # print("Upload directory:", upload_dir)
    # print("Amount of vectors: {}".format(len(vectors)))
    # print("Amount of rasters: {}".format(len(rasters)))
    # print("Amount of other data: {}".format(len(other_data)))

    # # get geoserver_data for looking up vector sld's
    # clip_geom = vector_to_geom(area_path, epsg=3857)

    # # extract vector data from their respective sources
    # extract_succes, extract_failure = extract_vector_data(
    #     vectors, temp_dir, organisatie
    # )

    # # make them upload ready
    # ready_succes, ready_failure = upload_ready(
    #     temp_dir, upload_dir, clip_geom, organisatie, bo_nummer, epsg=3857
    # )

    # # upload them to the geoserver
    # upload_data(
    #     upload_dir, bo_nummer, organisatie, eigen_naam, project_nummer
    # )

    # # create wms layers
    # wmslayer_succes, wmslayer_failures = create_wmslayers(
    #     upload_dir, setting.organisatie, setting.dataset, use_nens=True
    # )

    # # copy rasterstore, add clip and add to dataset
    # # cannot find correct stores
    # organisations = ["Provincie Zuid-Holland", "Nelen & Schuurmans"]
    # rasters = get_uuid_by_organisations(rasters, organisations)

    # rasters[0]["uuid"] = "197c72b9-3f64-440c-9025-3883fef94316"
    # rasters[1]["uuid"] = "f28bb892-20cb-4a31-90c8-5f6cd715ddbe"
    # rasters[2]["uuid"] = "5d3fc11c-5819-419a-85be-a53fa945c926"
    # rasters[3]["uuid"] = "9b40ef35-05bd-4473-a8cf-83338bdbb210"
    # rasters[4]["uuid"] = "cf09302b-0228-4220-b5a4-b7b5461f7fcf"
    # rasters[5]["uuid"] = "0d7fdf72-3f22-40b8-85ab-419acaba446d"
    # rasters[6]["uuid"] = "5aad9db6-7b71-49aa-9759-7dad26802c3c"
    # rasters[7]["uuid"] = "f50e8ad6-66cf-4247-9188-7cde3c0e976f"
    # rasters[7]["slug"] = rasters[7]["slug"].split(",")[1]
    # rasters[8]["uuid"] = "1d65a4e1-ac2f-4e66-9e52-1d130d870a34"
    # rasters[9]["uuid"] = "9c6f0130-001b-4747-9c9f-2a65b9370b32"

    # raster_succes, raster_failures = atlas2catalogue_rasterstores(
    #     rasters,
    #     raster_clip_id,
    #     bo_nummer,
    #     organisatie,
    #     dataset,
    #     overwrite=False,
    # )
