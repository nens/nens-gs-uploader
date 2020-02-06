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


#
#
#
#
# clip = {
#            "gemeente_ids": [
#                "geoblocks.raster.sources.RasterStoreSource",
#                "file:///119-fs-c02/raster-production/stores/nelen-schuurmans/gemeente-ids-2019-vdssnjxo"
#            ],
#            "area_of_interest_1": [
#                "geoblocks.raster.misc.Reclassify",
#                "gemeente_ids",
#                    [
#                    [27251, 1],
#                    [27289, 1],
#                    [27253, 1],
#                    [27290, 1],
#                    [27254, 1],
#                    [27291, 1],
#                    [27255, 1],
#                    [27292, 1],
#                    [27293, 1],
#                    [27257, 1],
#                    [27294, 1],
#                    [27258, 1],
#                    [27295, 1],
#                    [27259, 1],
#                    [27296, 1],
#                    [27297, 1],
#                    [27262, 1],
#                    [27264, 1],
#                    [27266, 1],
#                    [27267, 1],
#                    [27268, 1],
#                    [27269, 1],
#                    [27270, 1],
#                    [27273, 1],
#                    [27276, 1],
#                    [27278, 1],
#                    [24168, 1],
#                    [27280, 1],
#                    [24170, 1],
#                    [27282, 1],
#                    [27284, 1],
#                    [27285, 1],
#                    [50000, 0]]
#                                    ,
#                True
#            ],
#            "endpoint": [
#            "geoblocks.raster.misc.Clip",
#            "{input_block}",
#            "area_of_interest_1"]
#  }
#
# clip = {
#        "graph": {
#            "input_block": [
#                "geoblocks.raster.sources.RasterStoreSource",
#                "file:///119-fs-c02/raster-production/stores/nelen-schuurmans/hittestress-nederland"
#                ],
#            "input_raster": [
#                "geoblocks.raster.misc.MaskBelow",
#                "input_block",
#                0.001
#            ],
#            "gemeente_ids": [
#                "geoblocks.raster.sources.RasterStoreSource",
#                "file:///119-fs-c02/raster-production/stores/nelen-schuurmans/gemeente-ids-2019-vdssnjxo"
#            ],
#            "area_of_interest_1": [
#                "geoblocks.raster.misc.Reclassify",
#                "gemeente_ids",
#                    [
#                    [27251, 1],
#                    [27289, 1],
#                    [27253, 1],
#                    [27290, 1],
#                    [27254, 1],
#                    [27291, 1],
#                    [27255, 1],
#                    [27292, 1],
#                    [27293, 1],
#                    [27257, 1],
#                    [27294, 1],
#                    [27258, 1],
#                    [27295, 1],
#                    [27259, 1],
#                    [27296, 1],
#                    [27297, 1],
#                    [27262, 1],
#                    [27264, 1],
#                    [27266, 1],
#                    [27267, 1],
#                    [27268, 1],
#                    [27269, 1],
#                    [27270, 1],
#                    [27273, 1],
#                    [27276, 1],
#                    [27278, 1],
#                    [24168, 1],
#                    [27280, 1],
#                    [24170, 1],
#                    [27282, 1],
#                    [27284, 1],
#                    [27285, 1],
#                    [50000, 0]]
#                                    ,
#                True
#            ],
#            "endpoint": [
#            "geoblocks.raster.misc.Clip",
#            "input_raster",
#            "area_of_interest_1"]
#        },
#        "name": "endpoint"
#    }
#
# work = {  "graph": {
#                              "input":  [
#                                        "geoblocks.raster.sources.RasterStoreSource",
#                                        "file:///119-fs-c02/raster-production/stores/nelen-schuurmans/test_test_ghg_2050"
#                                ],
#
#                              "end":[
#                                  "geoblocks.raster.misc.MaskBelow",
#                                  "input",
#                                  0.1
#                                ]
#
#                            },
#                    "name": "end"
#
#                }
#
# clip_block = {
#            "graph": {
#                "input_raster": [
#                    "geoblocks.raster.sources.RasterStoreSource",
#                    input_store_url, #"file:///119-fs-c02/raster-production/stores/nelen-schuurmans/hittestress-nederland"
#                ],
#                "gemeente_ids": [
#                    "geoblocks.raster.sources.RasterStoreSource",
#                    "file:///119-fs-c02/raster-production/stores/nelen-schuurmans/gemeente-ids-2019-vdssnjxo"
#                ],
#                "area_of_interest_1": [
#                    "geoblocks.raster.misc.Reclassify",
#                    "gemeente_ids",
#                        [nummers,
#                        [50000, 0]]
#                                        ,
#                                True
#                ],
#                "endpoint": [
#                "geoblocks.raster.misc.Clip",
#                "input_raster",
#                "area_of_interest_1"]
#            },
#            "name": "endpoint"
#        }
