# -*- coding: utf-8 -*-
"""
Created on Thu May 16 16:55:29 2019

@author: chris.kerklaan
"""
# system imports
import sys

# relevant paths
import requests
from tqdm import tqdm


class wrap_atlas:
    def __init__(self, atlas_name):
        self.atlas_name = atlas_name
        self.atlassen = [
            "wpn",
            "zundert",
            "westland",
            "wdodelta",
            "velsen",
            "schiedam",
            "rijswijk",
            "rijnland",
            "purmerend",
            "polder",
            "oss",
            "middelburg",
            "mra",
            "meerdijk",
            "maastricht",
            "lv",
            "zuid-holland",
            "houten",
            "haarlemmermeer",
            "hhnk",
            "groningen",
            "etten",
            "denhaag",
            "delfland",
            "capelleaandenijssel",
            "bluelabel",
            "alphenaandenrijn",
            "almere",
            "alkmaar",
            "a5h",
            "agv",
        ]

    def get_json(self, atlas):
        atlas_api = f"https://{atlas}.klimaatatlas.net/api/"
        r = requests.get(atlas_api)
        self.atlas_api_json = r.json()
        return self.atlas_api_json

    def get_layer_list(self, atlas):
        self.atlas_api_json = self.get_json(atlas)
        self.atlas_maps = self.atlas_api_json["maps"]
        self.layers = []
        for maps in self.atlas_maps:
            maplayers = maps["mapLayers"]
            for maplayer in maplayers:
                yield maplayer

    #                url_split  = maplayer['url'].split("/")
    #                workspace = url_split[-2]
    #                layer_split = maplayer['layerName'].split(":")
    #                layer_name = layer_split[-1]

    #                yield ( {"atlas":self.atlas_api_json["title"],
    #                         "mapname":      maps["name"],
    #                         "layername":    layer_name,
    #                         "workspace":    workspace,
    #                         "slug":         workspace +":" + layer_name,
    #                         "wms":          maplayer['url']}
    #                        )

    def get_all_layers(self):
        self.all_layers = []
        for atlas in tqdm(self.atlassen):
            self.all_layers = self.get_layer_list(atlas)
        return self.all_layers

    def find_layers_in_all_atlasses(self, key, value):

        present_in_atlas = []
        for atlas in tqdm(self.atlassen):
            for layer in wrap.get_layer_list(atlas):
                if layer[key] == value:
                    present_in_atlas.append(atlas)
        return present_in_atlas


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


if __name__ == "__main__":
    wrap = wrap_atlas("zundert")
    json = wrap.get_json("zundert")

    atlas_present = []
    wrap = wrap_atlas("zundert")
    for atlas in tqdm(wrap.atlassen):
        for layer in wrap.get_layer_list(atlas):
            if "Bodem" == layer["layername"]:
                print(atlas)
                atlas_present.append(atlas)

    all_layers = atlas.get_all_layers()
