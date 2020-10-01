# -*- coding: utf-8 -*-
"""
Created on Mon Sep 23 10:29:05 2019

@author: chris.kerklaan
Tool & cmd tool to publish wmslayers in Lizard
"""
# Third-party imports
import json
from requests import get, post, codes, delete

# Local imports
from core.wrap import wrap_geoserver
from core.credentials import username, password

# GLOBALS
LEGEND_OPTIONS = (
    "LEGEND_OPTIONS=forceRule:True;dx:0.2;dy:0.2;mx:0.2;my:0.2"
    ";fontName:Times%20New%20Roman;borderColor:#429A95;border:true;"
    "fontColor:#15EBB3;fontSize:18;dpi:180"
)


class wmslayers(object):
    def __init__(self, username=username, password=password):
        self.username = username
        self.password = password
        self.wmslayer_url = "https://demo.lizard.net/api/v4/wmslayers/"
        self.wmslayer_uuid = "https://demo.lizard.net/api/v4/wmslayers/{uuid}/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"

        self.get_headers = {
            "username": username,
            "password": password,
            "Content-Type": "application/json",
        }
        self.post_headers = {"username": username, "password": password}
        self.nens_id = "61f5a464-c350-44c1-9bc7-d4b42d7f58cb"

    def get_nens_id(self):
        self.organisation_uuid = "61f5a464-c350-44c1-9bc7-d4b42d7f58cb"
        return self.organisation_uuid

    def get_organisation_id(self, organisation):
        r = get(
            url=self.organisation_url,
            headers=self.post_headers,
            params={"name__icontains": organisation},
        )
        if r.json()["count"] == 0:
            print("zero results for", organisation)
            print("using Nelen & Schuurmans as organisation")
            self.organisation_uuid = self.get_nens_id()

        elif r.json()["count"] > 1:
            print("count search results more than 1", r.json())
            print("using Nelen & Schuurmans as organisation")
            self.organisation_uuid = self.get_nens_id()

        else:
            self.organisation_uuid = r.json()["results"][0]["uuid"]

        return self.organisation_uuid

    def get_layer(self, name):

        r = get(
            url=self.wmslayer_url,
            headers=self.post_headers,
            params={"name__icontains": name},
        )

        results_exists = r.json()["count"] > 0
        slug_exists = False
        slug_result = None

        if results_exists:
            for result in r.json()["results"]:
                layer_name = result["name"]
                if layer_name == name:
                    return result, True

        return slug_result, slug_exists

    def get_download_url(self, wms_path, slug, epsg="28992"):
        return (
            "{}?&request=GetFeature&typeName={}&srsName="
            "epsg:{}&OutputFormat=shape-zip"
        ).format(wms_path.replace("wms", "wfs"), slug, epsg)

    def get_legend_url(self, wms_path, slug):
        return (
            "{}?REQUEST=GetLegendGraphic&VERSION=1.0.0&" "FORMAT=image/png&LAYER={}&{}"
        ).format(wms_path, slug, LEGEND_OPTIONS)

    def delete(self, uuid):

        r = delete(url=self.wmslayer_uuid.format(uuid=uuid), headers=self.get_headers)
        if r.status_code == 204:
            print("delete store succes", r.status_code)
        else:
            print("delete store failure:", r.json())

    def create(self, configuration, overwrite=False):
        _json, store_exists = self.get_layer(configuration["slug"])

        if not store_exists:
            # configuration["organisation"] = self.organisation_uuid
            r = post(
                url=self.wmslayer_url,
                data=json.dumps(configuration),
                headers=self.get_headers,
            )

            if not r.status_code == 201 or not r.status_code == 201:
                print("create store failure", r.status_code)
                print(r.json())
                return r.json()

            else:
                self.wmslayer_uuid = r.json()["uuid"]
                print("create store succes", r.status_code)
                return r.json()

        else:
            self.wmslayer_uuid = _json["uuid"]
            print(
                "rasterstore already exists, overwrite is false,"
                "thus using existing store"
            )
            return _json["wms_info"]

    def post_data(self, path):
        url = self.wmslayer_url + self.wmslayer_uuid + "/data/"

        r = post(url=url, files={"file": open(path, "rb")}, headers=self.post_headers)

        if not r.status_code == codes.ok:
            print("post data failure", r.status_code)
            print(r.json())

        else:
            print("post data succes", r.status_code)

    def atlas2wms(
        self, atlas_dict, organisation_uuid, dataset, supplier, organisation, product
    ):

        # correct data
        name = atlas_dict["name"][:80]
        slug_org = "_".join([organisation.lower(), product.lower()])
        slug_or = atlas_dict["slug"].lower().split(":")[-1]
        slug = ":".join([slug_org, slug_or])[:64]
        description = strip_information(atlas_dict["information"])

        self.configuration = {
            "name": name,
            "description": description,
            "slug": slug,
            "tiled": True,
            "wms_url": atlas_dict["url"],
            "access_modifier": 0,
            "supplier": supplier,
            "options": {"transparent": "true"},
            "shared_with": [],
            "datasets": [dataset],
            "organisation": organisation_uuid,
            "download_url": self.get_download_url(
                atlas_dict["url"], atlas_dict["slug"]
            ),
        }

    def geoserver2wms(
        self, geoserver, slug, supplier, dataset, organisation_uuid=None, access=0
    ):
        server = wrap_geoserver(geoserver)
        server.get_layer(slug, easy=False)

        if organisation_uuid is None:
            organisation_uuid = self.nens_id

        latlon_bbox = server.layer_latlon_bbox
        bounds = {
            "south": latlon_bbox[2],
            "west": latlon_bbox[0],
            "north": latlon_bbox[3],
            "east": latlon_bbox[1],
        }

        self.configuration = {
            "name": server.layer_title,
            "description": server.layer_abstract,
            "slug": slug[:64],
            "tiled": True,
            "wms_url": server.wms,
            "access_modifier": access,
            "supplier": supplier,
            "options": {"transparent": "true"},
            "shared_with": [],
            "datasets": [dataset],
            "organisation": organisation_uuid,
            "download_url": self.get_download_url(server.wms, slug),
            "spatial_bounds": bounds,
            "legend_url": self.get_legend_url(server.wms, slug),
            "get_feature_info_url": server.wms,
            "get_feature_info": True,
        }


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
    pass
