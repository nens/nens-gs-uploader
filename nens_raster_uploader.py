# -*- coding: utf-8 -*-
"""
Created on Fri Aug 23 14:20:37 2019

@author: chris.kerklaan
TODO:

    1. Overwrite metadata
    2. Add to dataset
    3. Voeg colormap toe
    4. add rasterstore

"""

# system imports
import os
import sys
import json
import logging
from time import sleep
from configparser import RawConfigParser

# Third-party imports
import argparse
from glob import glob

# Local imports
from nens_raster_uploader.project import (
    logger,
    log_time,
    percentage,
    print_list,
    print_dictionary,
)

from nens_raster_uploader.rasterstore import rasterstore
from nens_raster_uploader.edits import retile
from nens_raster_uploader.geoblocks import geoblock_clip, uuid_store

# Logging configuration options
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# test files
# inifile = "C:/Users/chris.kerklaan/tools/nens_raster_uploader/data/instellingen_voorbeeld.ini"
# sys.path.append("C:/Users/chris.kerklaan/tools")


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inifile", metavar="INIFILE", help="Settings voor inifile.")
    return parser


def get_file_name_from_path(path):
    return path.split("\\")[-1]


def set_log_config(location, name="log"):
    path = os.path.join(location, name)
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=path + ".log",
        level=logging.DEBUG,
    )


class settings_object(object):
    """Reads settings from inifile settings from command line tool"""

    def __init__(self, ini_file=None):
        if ini_file is not None:
            config = RawConfigParser()
            config.read(ini_file)
            self.ini = ini_file
            self.ini_location = os.path.dirname(ini_file)
            self.config = config

    def set_project(self):
        self.set_values("project")
        self.set_values("input_directory")
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


def add_output_settings(setting):
    file_name = get_file_name_from_path(setting.in_path)

    if file_name.split(".")[1] == "json":
        setting.json = True
        setting.json_dict = json.load(open(setting.in_path))
        setting.store.atlas2store(setting.json_dict, setting.eigen_naam)
        setting.configuration = setting.store.configuration
        setting.skip = False
        setting.onderwerp = setting.json_dict["atlas"]["name"]

    else:
        setting.set_values(file_name)

        if setting.project:
            add_on = "p"
        else:
            add_on = setting.bo_nummer

        in_name = "{}_{}_{}".format(add_on, setting.organisatie, setting.onderwerp)
        abstract_data = """
            De laag {omschrijving} komt van {bron}. Voor meer informatie over 
            deze laag, ga naar de klimaatatlas www.{bron}.klimaatatlas.net. 
            """.format(
            omschrijving=setting.onderwerp.lower(), bron=setting.organisatie.lower()
        )

        styles = {
            "styles": "{}:{}:{}".format(
                setting.style, setting.style_min, setting.style_max
            )
        }

        configuration = {
            "name": in_name,
            "observation_type": setting.observation_type,
            "description": abstract_data,
            "supplier": setting.eigen_naam,
            "supplier_code": in_name,
            "aggregation_type": 2,
            "options": styles,
            "acces_modifier": 0,  # public
            "rescalable": str(setting.rescalable).lower()
            #  "source":
        }
        setting.configuration = configuration

    if not setting.organisatie_uuid is None:
        setting.configuration.update({"organisation": setting.organisatie_uuid})
    else:
        setting.configuration.update(
            {"organisation": setting.store.get_organisation_uuid("nelen")}
        )

    if not setting.dataset is None:
        setting.configuration.update({"datasets": [setting.dataset]})

    slug = "{}:{}".format(
        setting.organisatie.lower(), setting.configuration["name"].lower()
    )
    setting.configuration.update({"slug": slug})

    return setting


def batch_upload(inifile):
    """ Returns batch upload shapes for one geoserver """
    setting = settings_object(inifile)
    setting.set_project()

    # set logging
    set_log_config(setting.ini_location)
    sys.stdout = logger(setting.ini_location)

    in_paths = glob(setting.directory + "/*.tif")
    in_paths = in_paths + glob(setting.directory + "/*.vrt")
    in_paths = in_paths + glob(setting.directory + "/*.json")

    present_paths = []
    for path in in_paths:
        file_name = get_file_name_from_path(path)
        if file_name.split(".")[1] == "json":
            present_paths.append(path)
        if file_name in setting.config.sections():
            present_paths.append(path)

    setting.store = rasterstore()
    print_list(present_paths, "Paths")

    failures = {}
    succes = {}
    for count, path in enumerate(present_paths):
        log_time("info", percentage(count, len(present_paths)), path, "l")

        setting.in_path = path
        setting = add_output_settings(setting)

        if not setting.skip:
            print_dictionary(setting.__dict__, "Settings")
            #            try:
            succes[setting.onderwerp] = upload(setting)
    #
    #            except Exception as e:
    #                print(e)
    #                failures[setting.onderwerp] = e

    # log_time("info", "sleeping to decrease load on server....")
    # sleep(30)

    print_dictionary(succes, "Succes")
    print_dictionary(failures, "Failures")


def upload(setting):
    if setting.clip:
        clip_numbers = json.loads(setting.clip_nummers)
        geoblock = uuid_store(setting.json_dict["rasterstore"]["uuid"])
        graph = geoblock_clip(geoblock, clip_numbers)
        setting.configuration["source"] = {"graph": graph, "name": "endpoint"}

    if setting.update_metadata_only:
        wms = setting.store.create(setting.configuration, setting.overwrite)

    elif setting.update_data_only:
        for raster_part in retile(setting.in_path):
            sleep(10)
            setting.store.post_data(raster_part)

    else:
        wms = setting.store.create(setting.configuration, setting.overwrite)
        for raster_part in retile(setting.in_path):
            setting.store.post_data(raster_part)
    sleep(15)

    wms = None
    return wms


if __name__ == "__main__":
    batch_upload(**vars(get_parser().parse_args()))
