# -*- coding: utf-8 -*-
"""
Created on Tue Sep 17 13:48:26 2019

@author: chris.kerklaan
https://dask-geomodeling.readthedocs.io/en/latest/raster.html
"""


def clip_gemeentes(input_block, gemeentes):
    nummers = []

    for gemeente in gemeentes:
        nummers.append([gemeente, 1])

    clip_block = {
        "gemeente_ids": [
            "geoblocks.raster.sources.RasterStoreSource",
            "file:///mnt/rastprod/stores/nelen-schuurmans/2019-gemeente-ids-3yz1ll9j",
        ],
        "area_of_interest_1": [
            "geoblocks.raster.misc.Reclassify",
            "gemeente_ids",
            nummers + [[50000, 0]],
            True,
        ],
        "endpoint": [
            "geoblocks.raster.misc.Clip",
            "{}".format(input_block),
            "area_of_interest_1",
        ],
    }

    return clip_block


def clip_provincies(input_block, provincies):
    nummers = []

    for provincie in provincies:
        nummers.append([provincie, 1])

    clip_block = {
        "gemeente_ids": [
            "geoblocks.raster.sources.RasterStoreSource",
            "file:///mnt/rastprod/stores/nelen-schuurmans/2019-provincie-ids-9dwte8yk",
        ],
        "area_of_interest_1": [
            "geoblocks.raster.misc.Reclassify",
            "gemeente_ids",
            nummers + [[50000, 0]],
            True,
        ],
        "endpoint": [
            "geoblocks.raster.misc.Clip",
            "{}".format(input_block),
            "area_of_interest_1",
        ],
    }

    return clip_block


def clip_waterschappen(input_block, waterschappen):
    nummers = []

    for waterschap in waterschappen:
        nummers.append([waterschap, 1])

    clip_block = {
        "gemeente_ids": [
            "geoblocks.raster.sources.RasterStoreSource",
            "file:///mnt/rastprod/stores/nelen-schuurmans/2019-waterschappen-ids-8mqsh79x",
        ],
        "area_of_interest_1": [
            "geoblocks.raster.misc.Reclassify",
            "gemeente_ids",
            nummers + [[50000, 0]],
            True,
        ],
        "endpoint": [
            "geoblocks.raster.misc.Clip",
            "{}".format(input_block),
            "area_of_interest_1",
        ],
    }

    return clip_block


def uuid_store(uuid):
    return {
        "graph": {"store": ["lizard_nxt.blocks.LizardRasterSource", uuid]},
        "name": "store",
    }


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
