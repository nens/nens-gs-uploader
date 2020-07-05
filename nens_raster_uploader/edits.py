# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 14:23:13 2019

@author: chris.kerklaan
"""

import os
import shutil
from nens_raster_uploader.gdal_retile import main


def retile(raster_path, retile_dir):
    temporary_directory = os.path.join(retile_dir, "temp")
    if os.path.exists(temporary_directory):
        shutil.rmtree(temporary_directory)
    os.mkdir(temporary_directory)
    # print(raster_path, temporary_location)
    print("retiling", raster_path)
    print("current count in directory", len(os.listdir(temporary_directory)))

    main(
        [
            "",
            "-ps",
            "10000",
            "10000",
            "-co",
            "COMPRESS=DEFLATE",
            "-targetDir",
            r"{}".format(temporary_directory),
            r"{}".format(raster_path),
        ]
    )

    tiles = []
    for i in os.listdir(temporary_directory):
        tiles.append(os.path.join(temporary_directory, i))

    return tiles
