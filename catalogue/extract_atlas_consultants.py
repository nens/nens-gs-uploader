# -*- coding: utf-8 -*-
"""
Created on Tue Feb  4 13:40:01 2020

@author: chris.kerklaan

Extract atlas data for consultants

TODO:
    1. Extract raw data for raster
    
Done:
    1. Added external scripts
    2. Add log_time
    3. Cleaned scripts

"""

# System imports
import os
import sys

# Third-party imports
import ogr
import math
import urllib
import json
from requests import get
from tqdm import tqdm

from urllib.request import urlretrieve
from owslib.wms import WebMapService

# Local imports
from catalogue.project import log_time, mk_dir
from catalogue.wrap import SERVERS, wrap_geoserver
from catalogue.vector import vector as vector_wrap, POLYGON
from catalogue.sld import wrap_sld
from catalogue.klimaatatlas import wrap_atlas
from catalogue.rasterstore import rasterstore
from catalogue.geoblocks import clip_gemeentes
from catalogue.rasterstore import StoreNotFound

# Exceptions
class MissingSLD(Exception):
    pass


class DownloadFailure(Exception):
    pass


class VectorOutsideArea(Exception):
    pass


def has_numbers(string):
    return any(char.isdigit() for char in string)


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


def feature_count_outside_geometry(path, atlas_geom):
    outside_count = 0
    gs_vect = vector_wrap(path)
    for feature in tqdm(gs_vect.layer):
        geom = feature.geometry()
        if not geom.Centroid().Within(atlas_geom):
            outside_count += 1
    return outside_count


def get_atlas_data(atlas_name):
    """ returns all atlas data """
    atlas = wrap_atlas(atlas_name)
    data = {"vector": [], "raster": [], "external": []}

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

        elif "lizard" not in layer["url"]:
            data["external"].append(layer)
        else:
            print("Could not assign", layer["url"])

    return data


def geoblock_clip(geoblock, clip_list):
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


def wms_bbox(vector):
    """ return bbox of wms layer in geoserver"""
    wms = WebMapService(vector["url"])
    return wms[vector["layername"]].boundingBoxWGS84


def bbox1_in_bbox2(bbox1, bbox2):
    """ boolean test if ogr envelope bbox1 in bbox2"""

    if (
        (bbox2[0] <= bbox1[0] <= bbox2[1])
        and (bbox2[0] <= bbox1[1] <= bbox2[1])
        and (bbox2[2] <= bbox1[2] <= bbox2[3])
        and (bbox2[2] <= bbox1[3] <= bbox2[3])
    ):
        return True
    else:
        return False


def wms_in_extent(vector, extent_geom, buffer=0.1):
    """ checks if vector layer within extent """
    bounds = wms_bbox(vector)
    bbox_vector = (bounds[0], bounds[2], bounds[1], bounds[3])
    extent_buff = extent_geom.Buffer(buffer)
    bbox_extent = extent_buff.GetEnvelope()
    return bbox1_in_bbox2(bbox_vector, bbox_extent)


def set_geoserver_connections(vectors):
    geoservers = []
    for vector in vectors:
        geoservers.append(vector["geoserver"])

    gs_dict = {}
    for geoserver in list(set(geoservers)):
        gs_dict[geoserver] = wrap_geoserver(geoserver, easy=True)

    return gs_dict


def partly_downloads(url, slug, dst, x1="", x2="", y1="", y2=""):
    max_download = 100000
    total = index_wfs_download(url, slug, 0, 1, x1, x2, y1, y2)["totalFeatures"]
    downloads = math.ceil(total / max_download)
    idx = 0
    full = {
        "type": "FeatureCollection",
        "features": [],
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},},
    }
    print("Starting partly collection of features")
    for d in tqdm(range(downloads)):
        full["features"] = (
            full["features"]
            + index_wfs_download(url, slug, idx, max_download, x1, x2, y1, y2)[
                "features"
            ]
        )
        idx = idx + max_download

    with open(dst, "w") as f:
        json.dump(full, f)


def index_wfs_download(url, slug, start, count, x1="", x2="", y1="", y2=""):
    cmd = (
        "{url}?&request=GetFeature&typeName={slug}&srsName=epsg:4326"
        "&bbox={x1},{y1},{x2},{y2},epsg:4326&count={count}"
        "&startIndex={startindex}&OutputFormat=json"
    ).format(
        url=url, slug=slug, x1=x1, x2=x2, y1=y1, y2=y2, startindex=start, count=count,
    )
    r = get(cmd)
    return json.loads(r.content)


def download_vector(vector, temp_dir, dst_json, x1="", x2="", y1="", y2=""):
    download_url = (
        "{url}?&request=GetFeature&typeName={slug}&srsName=epsg:4326"
        "&bbox={x1},{y1},{x2},{y2},epsg:4326&OutputFormat=application/json"
    ).format(
        url=vector["url"].replace("wms", "wfs"),
        slug=vector["slug"],
        x1=x1,
        x2=x2,
        y1=y1,
        y2=y2,
    )

    dst_shp = dst_json.replace(".geojson", ".shp")

    try:
        urlretrieve(download_url, dst_json)
    except urllib.error.HTTPError:
        partly_downloads(
            vector["url"].replace("wms", "wfs"),
            vector["slug"],
            dst_json,
            x1="",
            x2="",
            y1="",
            y2="",
        )
    try:
        dst_vector = vector_wrap(dst_json)
    except TypeError as e:
        raise DownloadFailure(
            "Json downloaden, but cannot be converted to" "shapefile", e
        )

    dst_vector.write(dst_shp, dst_vector.layer)
    return dst_json


def retrieve_sld(vector, gs_dict, path):
    try:
        gs_dict[vector["geoserver"]].get_layer(vector["slug"])
    except AttributeError:
        raise MissingSLD("SLD not found for {}".format(vector["slug"]))
    sld_body = gs_dict[vector["geoserver"]].sld_body
    vector_sld = wrap_sld(sld_body, "body")
    vector_sld.write_xml(path)


def extract_vectors(vectors, temp_dir, organisation, clip_geom, download=False):

    extract_data_failures = []
    extract_data_succes = []
    bbox = clip_geom.GetEnvelope()
    wkt = POLYGON.format(x1=bbox[0], x2=bbox[1], y1=bbox[2], y2=bbox[3])
    bbox_geom = ogr.CreateGeometryFromWkt(wkt)

    log_time("info", "Set geoserver connections")
    gs_dict = set_geoserver_connections(vectors)

    log_time("info", "Extracting vector data")
    for vector in tqdm(vectors):
        try:
            log_time("info", "Processing vector:", vector["name"])
            json_dict = {}

            subject = get_subject_from_name(vector["layername"], vector["workspace"])

            meta_path_exists = False
            meta_path = os.path.join(temp_dir, subject + ".json")
            if os.path.exists(meta_path):
                log_time("info", "Meta file exists, skipping", subject)
                meta_path_exists = True
                continue

            retrieve_sld(vector, gs_dict, meta_path.replace(".json", ".sld"))

            if not wms_in_extent(vector, bbox_geom) or download:
                log_time(
                    "info",
                    "Wms layer bbox outside area, retrieving raw data"
                    " or download = True",
                )
                download_vector(
                    vector, temp_dir, meta_path.replace(".json", ".geojson"), *bbox,
                )

                # log_time("info",'Checking feature count outside geometry')
                # count = feature_count_outside_geometry(meta_path.replace(
                #                                                  ".json",
                #                                                  ".shp"),
                #                                                   clip_geom)
                # if count > 0:
                raise VectorOutsideArea(f"Outside atlas area")

        except DownloadFailure as e:
            vector["error"] = "Download failure, message:{}".format(e)
            extract_data_failures.append(vector)

        except MissingSLD as e:
            vector["error"] = "missing sld body layer not in geoserver, {}".format(e)
            extract_data_failures.append(vector)

        except VectorOutsideArea as e:
            vector["error"] = "Vector outside ara, message:{}".format(e)
            extract_data_failures.append(vector)

        except RuntimeError as e:
            vector["error"] = "Vector has extract error {}".format(e)
            extract_data_failures.append(vector)

        except AttributeError as e:
            vector["error"] = "missing sld body layer not in geoserver, {}".format(e)
            extract_data_failures.append(vector)

        except json.JSONDecodeError as e:
            vector["error"] = "Vector has json error{}".format(e)
            extract_data_failures.append(vector)

        else:
            vector["subject"] = subject
            extract_data_succes.append(vector)

        finally:
            if not meta_path_exists:
                json_dict["atlas"] = vector
                with open(meta_path, "w") as outfile:
                    json.dump(json_dict, outfile)

    return extract_data_succes, extract_data_failures


def extract_rasters(rasters, temp_dir, atlas_name):

    raster_failures = []
    raster_succes = []

    store = rasterstore(update_slugs=True)

    # Start raster changes
    for raster in rasters:
        log_time("info", "Processing raster:", raster["name"])

        json_dict = {}
        subject = "_".join(raster["name"].lower().split(" "))

        meta_path_exists = False
        meta_path = os.path.join(temp_dir, subject + ".json")
        if os.path.exists(meta_path):
            log_time("info", "Meta file exists, skipping", subject)
            meta_path_exists = True
            continue

        try:
            uuid = store.get_uuid_by_slug(raster["slug"])
            store_configuration = store.get_store(uuid)

        except ValueError as e:
            raster["error"] = "Does this store exist? {} {}".format(raster["slug"], e)
            raster_failures.append(raster)

        except StoreNotFound as e:
            raster["error"] = "Does this store exist in lizard? {} {}".format(
                raster["slug"], e
            )
            raster_failures.append(raster)

        else:
            raster_succes.append(raster)

        finally:
            if not meta_path_exists:
                json_dict["rasterstore"] = store_configuration
                json_dict["atlas"] = raster
                with open(meta_path, "w") as outfile:
                    json.dump(json_dict, outfile)

    return raster_succes, raster_failures


def extract_external(externals, temp_dir):

    extract_data_failures = []
    extract_data_succes = []

    log_time("info", "Extracting externals metadata")
    for extern in tqdm(externals):
        try:
            log_time("info", "Processing external wms:", extern["name"])
            json_dict = {}

            meta_path = os.path.join(temp_dir, extern["name"] + ".json")

            if os.path.exists(meta_path):
                log_time("info", "Meta file exists, skipping", extern["name"])
                continue

        except Exception as e:
            extern["error"] = f"General error: {e}"
        else:
            extern["subject"] = extern["name"]
            extract_data_succes.append(extern)

        finally:
            json_dict["atlas"] = extern
            with open(meta_path, "w") as outfile:
                json.dump(json_dict, outfile)

    return extract_data_succes, extract_data_failures


def extract_atlas(atlas_name, wd, download):
    """ Returns batch upload shapes for one geoserver """

    os.chdir(wd)

    vector_dir = mk_dir(wd, folder_name="extract_vector")
    raster_dir = mk_dir(wd, folder_name="extract_raster")
    external_dir = mk_dir(wd, folder_name="extract_external")

    data = get_atlas_data(atlas_name)
    unique_data = unique(data)
    vectors = unique_data["vector"]
    rasters = unique_data["raster"]
    externals = unique_data["external"]

    log_time("info", "Raster directory:", raster_dir)
    log_time("info", "Vector directory:", vector_dir)
    log_time("info", "exteral wms directory:", external_dir)

    log_time("info", "Amount of vectors: {}".format(len(vectors)))
    log_time("info", "Amount of rasters: {}".format(len(rasters)))
    log_time("info", "Amount of external wms: {}".format(len(externals)))

    atlas = wrap_atlas(atlas_name)
    clip_geom = atlas.get_boundaring_polygon(atlas_name, "boundary", write=False)

    # extract vector data from their respective sources
    extract_vector_succes, extract_vector_failures = extract_vectors(
        vectors, vector_dir, atlas_name, clip_geom, download
    )

    extract_raster_succes, extract_raster_failures = extract_rasters(
        rasters, raster_dir, atlas_name,
    )
    extract_ext_succes, exteract_ext_failures = extract_external(
        externals, external_dir
    )

    return (
        vectors,
        rasters,
        externals,
        exteract_ext_failures,
        extract_raster_failures,
        extract_vector_failures,
    )


if __name__ == "__main__":
    pass
    # extract_atlas(**vars(get_parser().parse_args()))
