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
#from nens_raster_uploader.geoblocks import clip

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
    setting.set_values(file_name)


    in_name = "{}_{}_{}".format(
        setting.bo_nummer, setting.organisatie, setting.onderwerp
    )
    print(in_name)
    abstract_data = """
        De laag {omschrijving} komt van {bron}. Voor meer informatie over 
        deze laag, ga naar de klimaatatlas www.{bron}.klimaatatlas.net. 
        """.format(
        omschrijving=setting.onderwerp.lower(),
        bron=setting.organisatie.lower(),
    )

    styles = {
        "styles": "{}:{}:{}".format(
            setting.style, setting.style_min, setting.style_max
        )
    }

    configuration = {
        "name": in_name,
        "organisation": setting.store.get_nens_id(),
        "observation_type": setting.observation_type,
        "description": abstract_data,
        "supplier": setting.eigen_naam,
        "supplier_code": in_name,
        "aggregation_type": 2,
        "options": styles,
        "acces_modifier": 0, # public
        "rescalable": str(setting.rescalable).lower()
      #  "source":  
    }

    setting.configuration = configuration

    print_dictionary(setting.__dict__, "Settings")
    
    return setting


def batch_upload(inifile):
    """ Returns batch upload shapes for one geoserver """
    setting = settings_object(inifile)
    setting.set_project()

    # set logging
    set_log_config(setting.ini_location)
    sys.stdout = logger(setting.ini_location)

    in_paths = glob(setting.directory + "/*.tif")
    in_paths = in_paths  + glob(setting.directory + "/*.vrt")


    present_paths = []
    for path in in_paths:
        file_name = get_file_name_from_path(path)
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

#            try:
                succes[setting.onderwerp] = upload(setting)
#
#            except Exception as e:
#                print(e)
#                failures[setting.onderwerp] = e

    #log_time("info", "sleeping to decrease load on server....")
    #sleep(30)

    print_dictionary(succes, "Succes")
    print_dictionary(failures, "Failures")


def upload(setting):

    if setting.overwrite_store:
        _json, store_exists = setting.store.get_store(
                "nelen-schuurmans:" + setting.configuration['name'])

        if store_exists:
            setting.store.delete_store(_json["uuid"])
        else:
            print("store does not yet exist")

    #  create store
    if setting.update_metadata_only:
        wms = setting.store.create(setting.configuration, setting.overwrite)

    elif setting.update_data_only:
        for raster_part in retile(setting.in_path, setting.ini_location):
            sleep(10)
            setting.store.post_data(raster_part)

    else:
        wms = setting.store.create(setting.configuration, True)
#        setting.store.post_data(setting.in_path)
        for raster_part in retile(setting.in_path):
#            pass
            setting.store.post_data(raster_part)
    sleep(15)

    wms = None
    return wms


if __name__ == "__main__":
    batch_upload(**vars(get_parser().parse_args()))
