# -*- coding: utf-8 -*-
"""
Created on Fri Jul 26 09:05:11 2019

@author: chris.kerklaan


atlas2catalogue vertaald een atlas naar een catalogus, voor zover mogelijk.

Stappen:
    1. vectors, rasters en andere data worden opgehaald uit een atlas.
    2. Vectors worden gecheckt op boundingbox.
    3. Valt de vector buiten de bbox, dan dient de data gedownload te worden.
    4. Check de data, is deze echt te groot? Upload deze dan opnieuw.
    4. Valt de vector binnen de bbox, dan wordt er een wmslayer aangemaakt.
    5. Rasters worden altijd geclipt en opnieuw geupload.
    6. Een summary (met errors) wordt gegenereerd.
    

TODO:
    1. Download all
    2. Downloaden van rasters
    3. Uploaden naar github
    4. Tools voor adviseurs
    5. Jelmer test


FIXES:
    1. Downloaden van geojson makkelijker voor gs dan Shape
    2. Log bestanden

"""

# Sytem imports
import os
import sys

# Third-party imports
import argparse
import ogr
import gdal
import logging
import json
from glob import glob
from tqdm import tqdm
from shutil import copyfile
from configparser import RawConfigParser


# Local imports
from catalogue.extract_atlas_consultants import extract_atlas
from catalogue.klimaatatlas import wrap_atlas
from catalogue.vector import vector as vector_wrap
from catalogue.project import logger, log_time, mk_dir
from catalogue.wmslayers import wmslayers
from catalogue.rasterstore import rasterstore
from catalogue.geoblocks import clip_gemeentes, uuid_store



# GLOBALS
# INSTELLINGEN_PATH = (
#     "C:/Users/chris.kerklaan/tools/atlas2catalogue/instellingen"
# )
# __file__ = "C:/Users/chris.kerklaan/tools/atlas2catalogue.py"
dir_path = os.path.dirname(os.path.realpath(__file__))
GEMEENTEN_PATH = os.path.join(
    dir_path, "catalogue", "data", "gemeentes_2019_4326_2.shp"
)
# inifile = (
#     "C:/Users/chris.kerklaan/tools/catalogue/instellingen/atlas2catalogue.ini"
# )


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inifile", metavar="INIFILE", help="Settings voor inifile.")
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

    def set_project(self):
        self.set_values("project")
        self.set_values("tool")

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


def has_numbers(string):
    return any(char.isdigit() for char in string)


def set_log_config(location, name="log"):
    path = os.path.join(location, name)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=path + ".log",
        level=logging.DEBUG,
    )
    gdal.SetConfigOption("CPL_LOG_ERRORS", path + "_gdal_err.log")
    gdal.SetConfigOption("CPL_LOG", path + "_gdal.log")


def summary(
    vectors,
    vector_extract_failures,
    wmslayer_failures,
    ready_failure,
    rasters,
    raster_extract_failures,
    rasterstore_failures,
    externals,
    externals_failures,
):
    log_time("info", "summary", "Found vectors in atlas {}".format(len(vectors)))
    for vector in vectors:
        print("\t" + vector["name"])

    log_time(
        "info",
        "summary",
        "Extract vector failures {}".format(len(vector_extract_failures)),
    )
    for vector in vector_extract_failures:
        print("\t{}:{}".format(vector["name"], vector["error"]))

    log_time(
        "info", "summary", "Upload-ready vector failures {}".format(len(ready_failure))
    )
    for vector in ready_failure:
        print("\t{}:{}".format(vector["name"], vector["error"]))

    log_time(
        "info", "summary", "Upload vector failures {}".format(len(wmslayer_failures))
    )
    for vector in wmslayer_failures:
        print("\t{}:{}".format(vector["name"], vector["error"]))

    log_time("info", "summary", "Found rasters in atlas {}".format(len(rasters)))
    for raster in rasters:
        print("\t" + raster["name"])

    log_time(
        "info",
        "summary",
        "Raster extract failures {}".format(len(raster_extract_failures)),
    )
    for raster in raster_extract_failures:
        print("\t{}:{}".format(raster["atlas"]["name"], raster["error"]))

    log_time(
        "info",
        "summary" "Upload to rasterstore failures {}".format(len(rasterstore_failures)),
    )
    for raster in rasterstore_failures:
        print("\t{}:{}".format(raster["rasterstore"]["name"], raster["error"]))

    log_time("info", "summary", "External wmslayers in atlas {}".format(len(externals)))
    for external in externals_failures:
        print("\t" + external["atlas"]["name"])


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


def get_clip_id(geom):

    ds = ogr.Open(GEMEENTEN_PATH)
    layer = ds[0]
    layer.SetSpatialFilter(geom)

    gemeenten_ids = []
    for feature in layer:
        if feature.geometry().PointOnSurface().Intersects(geom):
            gemeenten_ids.append(feature["id"])
    ds = None

    return gemeenten_ids


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

    block_clip = clip_gemeentes(input_block, clip_list)

    for key, value in graph.items():
        block_clip[key] = value

    return block_clip


def delete_excess_raster_info(config):
    # delete EXCESS
    excess = [
        "id",
        "spatial_bounds",
        "last_modified",
        "uuid",
        "projection",
        "origin_x",
        "origin_y",
        "writable",
        "wms_info",
        "pixelsize_x",
        "pixelsize_y",
        "rescalable",
        "interval",
        "temporal",
        "url",
        "shared_with",
        "datasets",
    ]
    for e in excess:
        del config[e]
    return config


def upload_ready_vectors(
    upload_dir, clip_geom, organisation, dataset, epsg=3857
):

    upload_ready_succes = []
    upload_ready_failures = []

    log_time("info", "upload ready vectors")
    for meta_path in tqdm(glob("extract_vector" + "\*.json")):

        vector_path = meta_path.replace(".json", ".shp")
        meta_data = json.load(open(meta_path))

        if "error" in meta_data["atlas"]:
            log_time("info", "Skipped {} due to error message".format(meta_path))
            continue

        vector_name = get_subject_from_name(
            os.path.basename(vector_path).split(".")[0], organisation
        )

        vector_length = 62
        vector_name_new = vector_name[:vector_length]
        meta_data["vector_name"] = vector_name_new

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

            log_time("info", "incomplete data", meta_data["extract_error"])

        except Exception:
            pass

        # if feature_store and os.path.exists(vector_path):
        #     fs_vector = vector_wrap(os.path.join(os.getcwd(), vector_path))
        #     fs_vector.correct(fs_vector.layer, epsg=epsg)
        #     fs_vector.clip(fs_vector.layer, clip_geom)
        #     output_file = os.path.join(upload_dir, vector_name_new + ".shp")
        #     fs_vector.write(
        #         output_file, fs_vector.layer, layer_name=vector_name_new
        #     )

        # copy sld
        if sld_store:
            sld_in = meta_path.replace(".json", ".sld")
            sld_out = os.path.join(upload_dir, vector_name_new + ".sld")
            #copyfile(sld_in, sld_out)

        meta_out = os.path.join(upload_dir, vector_name_new + ".json")
        with open(meta_out, "w") as out_file:
            json.dump(meta_data, out_file)

    return upload_ready_succes, upload_ready_failures


def create_wmslayers(upload_dir, setting, bounds, use_nens=False):

    wmslayer_failures = []
    wmslayer_succes = []

    for meta_path in glob(upload_dir + "/*.json"):
        try:
            
            wmslayer = wmslayers()
            meta_data = json.load(open(meta_path))

            name = meta_data["atlas"]["name"]

            log_time("info", f"Creating wms layer for {name}")

            wms_info, result_exists = wmslayer.get_layer(name)

            if result_exists:
                wmslayer.delete(wms_info["uuid"])

            if use_nens:
                setting.organisatie_uuid = wmslayer.get_nens_id()

            # set description
            if "information" in meta_data["atlas"]:
                wmslayer_description = strip_information(
                    meta_data["atlas"]["information"]
                )
            else:
                wmslayer_description = ""

            # set name of layer
            if "name" in meta_data["atlas"]:
                name = meta_data["atlas"]["name"][:80]
            else:
                name = name[:80]

            if "extract_error" in meta_data:
                if "coverage" in meta_data["extract_error"]:
                    error = True
                elif "sld" in meta_data["extract_error"]:
                    error = True
                else:
                    error = False
            else:
                error = False

            if error:
                continue

            slug = meta_data["atlas"]["slug"].lower()
            url = meta_data["atlas"]["url"]

            # download link
            download_url = "{}?&request=GetFeature&typeName={}&OutputFormat=application/json".format(
                url.replace("wms", "wfs"), slug
            )

            # legend link
            legend_link = (
                "{}?REQUEST=GetLegendGraphic&VERSION=1.0.0&"
                "FORMAT=image/png&LAYER={}&LEGEND_OPTIONS="
                "forceRule:True;dx:0.2;dy:0.2;mx:0.2;my:0.2;"
                "fontName:Times%20New%20Roman;borderColor:#429A95;"
                "border:true;fontColor:#15EBB3;fontSize:18;dpi:180"
            ).format(url, slug)
            bounding_box = {
                "south": bounds[2],
                "west": bounds[0],
                "north": bounds[3],
                "east": bounds[1],
            }

            configuration = {
                "name": name,
                "description": wmslayer_description,
                "slug": slug,
                "tiled": True,
                "wms_url": url,
                "access_modifier": 0,
                "supplier": setting.eigen_naam,
                "options": {"transparent": "true"},
                "shared_with": [],
                "datasets": [setting.dataset],
                "organisation": setting.organisatie_uuid,
                "download_url": download_url,
                "spatial_bounds": bounding_box,
                "legend_url": legend_link,
                "get_feature_info_url": url,
                "get_feature_info": True,
            }
        
            #x.append(configuration)
            meta_data["wmslayer"] = wmslayer.create(configuration, overwrite=True)

        except Exception as e:
            print(e)
            meta_data["error"] = e
            wmslayer_failures.append(meta_data)

        else:
            wmslayer_succes.append(meta_data)

    return wmslayer_succes, wmslayer_failures


def create_atlasstores(
    raster_dir, clip_list, setting, use_nens=False, overwrite=False,
):

    raster_failures = []
    raster_succes = []

    # Start raster changes

    for meta_path in glob(raster_dir + "/*.json"):
        raster = json.load(open(meta_path))

        log_time("info", "Processing rasterstore:", raster["atlas"]["name"])

        store = rasterstore()

        # copy rasterstore
        config = raster["rasterstore"]

        # add clip top copied rasterstore
        geoblock = uuid_store(config["uuid"])
        graph = geoblock_clip(geoblock, clip_list)
        config["source"] = {"graph": graph, "name": "endpoint"}

        # acces modifier
        config["access_modifier"] = 0

        # name
        config["name"] = raster["atlas"]["name"]

        # supplier
        config["supplier"] = setting.eigen_naam

        # Description
        config["description"] = strip_information(raster["atlas"]["information"])

        # observation type
        if "observation_type" in config and config["observation_type"]:
            if "code" in config["observation_type"]:
                code = config["observation_type"]["code"]
        else:
            code = "Waterdepth"

        config["observation_type"] = code

        # organisation
        if use_nens:
            config["organisation"] = "61f5a464-c350-44c1-9bc7-d4b42d7f58cb"
        else:
            config["organisation"] = setting.organisatie_uuid

        # slug search name
        slug_name = config["name"].replace(" ", "-").lower()
        slug = "{}:{}".format(setting.organisatie, slug_name)

        # format slug to 64 characters
        slug = slug[:64]

        # styles
        config = delete_excess_raster_info(config)

        # add datasets
        config["datasets"] = [setting.dataset]

        # add slug for search
        config["slug"] = slug

        # create stores
        try:
            store.create(config, overwrite=overwrite)

        except Exception as e:
            raster["error"] = e
            raster_failures.append(raster)
        else:
            raster_succes.append(raster)

    return raster_succes, raster_failures


def create_catalogue(inifile):
    """ Returns batch upload shapes for one geoserver """
    setting = settings_object(inifile)

    # set logging
    set_log_config(setting.ini_location)
    sys.stdout = logger(setting.ini_location)

    # setting.wd = "C:/Users/chris.kerklaan/Documents/temp_meta_only"
    # setting.download = False

    os.chdir(setting.wd)
    (
        vectors,
        rasters,
        externals,
        extract_ext_failures,
        extract_rast_failures,
        extract_vect_failures,
        
    ) = extract_atlas(setting.atlas_name, setting.wd, setting.download, setting.resolution)

    if setting.extract_only:
        return print("Finished extracting data")

    atlas = wrap_atlas(setting.atlas_name)
    clip_geom = atlas.get_boundaring_polygon(setting.atlas_name, "boundary")

    upload_dir = mk_dir(path=os.getcwd(), folder_name="upload_vector")
    ready_succes, ready_failure = upload_ready_vectors(
        upload_dir,
        clip_geom,
        setting.organisatie,
        dataset=setting.dataset,
    )

    # create wms layers
    wmslayer_succes, wmslayer_failures = create_wmslayers(
        upload_dir, setting, clip_geom.GetEnvelope()
    )

    wmslayer_succes, wmslayer_failures = create_wmslayers(
        "extract_external", setting, clip_geom.GetEnvelope()
    )

    raster_clip_ids = get_clip_id(clip_geom)
    raster_succes, raster_failures = create_atlasstores(
        "extract_raster", raster_clip_ids, setting, overwrite=True, use_nens=setting.use_nens,
    )
    summary(
        vectors,
        extract_vect_failures,
        wmslayer_failures,
        ready_failure,
        rasters,
        extract_rast_failures,
        raster_failures,
        externals,
        extract_ext_failures,
    )


if __name__ == "__main__":
    create_catalogue(**vars(get_parser().parse_args()))
