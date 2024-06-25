# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 12:01:43 2024

@author: ruben.vanderzaag

Stappen: 
    Voordat je het script draait: 
        1. Check of er een nieuwe organisatie aangemaakt moet worden of dat er een bestaande gebruikt kan worden
        2. Eventueel nieuwe organisatie aanvragen via Steven (en zelf Admin/supplier rechten krijgen)
        3. Het .ini bestandje vullen (dezelfde naam als dit script)
    
    In dit script:
        1. Een layer collection wordt aangemaakt. Alle lagen van de klimaatatlas worden toegevoegd aan deze layer collection, zodat ze makkelijk te vinden zijn.
        2. De lagen die geconfigureerd zijn in de Atlas worden uitgelezen.
        3. Er wordt onderscheid gemaakt tussen raster en vector lagen.
        4. Raster lagen staan al in Lizard. Deze worden toegevoegd aan de layer collection, op public gezet en de naam wordt aangepast o.b.v. de laagnaam in de Atlas.
        5. Vectorlagen staan in de geoserver, maar nog niet in Lizard. Deze worden geconfigureerd in Lizard. Elke WMS laag krijgt ook een download URL mee. 
        6. Wanneer een laag uit de Atlas niet goed geconfigureerd kon worden in Lizard, dan wordt deze toegevoegd aan de list 'failed_layers'. Als deze list leeg is, zijn alle lagen met succes geconfigureerd. 
           
"""

import requests
import numpy as np
from configparser import RawConfigParser
import os

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
        self.set_values("lizard")

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
        "**",
    ]

    for character in characters:
        information = information.replace(character, "")
    return information

def layer_collection_exists():
    lc_url = "https://nens.lizard.net/api/v4/layercollections/"
    query_lc = f"?slug={settings.layer_collection}" 
    lc_api = lc_url + query_lc
    lc_list = requests.get(lc_api).json()["results"]
    if np.size(lc_list) > 0:
        print(f"Layer collection {settings.layer_collection} already exists. Therefore, no new collection is created")
        return True
    else:
        print(f"Layer collection {settings.layer_collection} is created")
        return False

def make_new_layer_collection():
    #info ophalen van organisatie
    r = requests.get(f"https://nens.lizard.net/api/v4/organisations/{settings.organisation_uuid}")
    org_lizard_api_json = r.json()

    layer_collection_config = {
        "url": f"https://nens.lizard.net/api/v4/layercollections/{settings.layer_collection}",
        "slug": settings.layer_collection,
        "organisation": org_lizard_api_json["url"],
        "access_modifier": 0,
        "supplier": settings.supplier,
    }
    
    layer_collection_url = "https://nens.lizard.net/api/v4/layercollections/"
    if layer_collection_exists():
        requests.patch(url=layer_collection_url,json=layer_collection_config,headers=json_headers)
    else: 
        requests.post(url=layer_collection_url,json=layer_collection_config,headers=json_headers)

def maplayer_exists(name):
    wms_url = "https://nens.lizard.net/api/v4/wmslayers/"
    query_wmslayer = f"?name={name}" 
    wms_api = wms_url + query_wmslayer
    wms_list = requests.get(wms_api).json()["results"]
    if np.size(wms_list) > 0:
        print(f"{name} already exists. Therefore, no new layer is created")
        return True
    else:
        print(f"{name} is created")
        return False
    
def vector_to_wms(layer_collection_url,layer_collection_name,organisation_uuid,supplier,maplayer):
    wmslayer_description = strip_information(maplayer["information_markdown"])
    slug = maplayer["wms_layer_name"].lower()
    name = maplayer["display_name"]
    url = maplayer["layer_url"]
    download_url = "{}?&request=GetFeature&typeName={}&srsName=epsg:28992&OutputFormat=shape-zip".format(
        url.replace("wms", "wfs"), slug
        )
    legend_link = (
        "{}?REQUEST=GetLegendGraphic&VERSION=1.0.0&"
        "FORMAT=image/png&LAYER={}&LEGEND_OPTIONS="
        "forceRule:True;dx:0.2;dy:0.2;mx:0.2;my:0.2;"
        "fontName:Times%20New%20Roman;borderColor:#429A95;"
        "border:true;fontColor:#15EBB3;fontSize:18;dpi:180"
    ).format(url, slug)
    bounding_box = {
        "south": maplayer["extent"]["south"],
        "west": maplayer["extent"]["west"],
        "north": maplayer["extent"]["north"],
        "east": maplayer["extent"]["east"],
    }

    configuration = {
        "name": name + " [" + layer_collection_name + "]",
        "description": wmslayer_description,
        "slug": slug,
        "tiled": True,
        "wms_url": url,
        "access_modifier": 0,
        "supplier": settings.supplier,
        "options": {"transparent": "true"},
        "shared_with": [],
        "layer_collections": [f"{layer_collection_url}{layer_collection_name}/"],
        "organisation": organisation_uuid,
        "download_url": download_url,
        "spatial_bounds": bounding_box,
        "legend_url": legend_link,
        "get_feature_info_url": url,
        "get_feature_info": True,
    }
    wms_url = "https://nens.lizard.net/api/v4/wmslayers/"
    
    if maplayer_exists(configuration["name"]):
        requests.patch(url=wms_url,json = configuration,headers=json_headers)
    else:
        requests.post(url=wms_url,json = configuration,headers=json_headers)
    
def raster_to_layer_collection(layer_collection_url,layer_collection_name,organisation_uuid,supplier,maplayer_name,failed_layers,maplayer_display_name):
    configuration ={"layer_collections": [f"{layer_collection_url}{layer_collection_name}/"],
                    "access_modifier": 0,
                    "organisation": organisation_uuid,
                    "name":maplayer_display_name + " [" + layer_collection_name + "]",
                    }
    raster_url = "https://nens.lizard.net/wms/"
    raster_url_api = raster_url.split("/wms",1)[0]+"/api/v4/rasters/"
    raster_name = maplayer_name.split(":",1)[1]
    query_raster = f"?slug__icontains={raster_name}" 
    raster_api = raster_url_api + query_raster
    r = requests.get(raster_api)
    raster_api_json = r.json()
    raster_list = raster_api_json["results"]
    if np.size(raster_list) == 1:
        raster_uuid = raster_list[0]["uuid"]
    elif np.size(raster_list) >1: #Checken of dit altijd opgaat
        for j in range(0,np.size(raster_list)):
            raster_slug = raster_list[j]["wms_info"]["layer"]
            if maplayer_name == raster_slug:
                raster_uuid = raster_list[j]["uuid"]      
    else: #Kan dit?
        print(f"RASTER NOT FOUND ({raster_name})")
        failed_layers.append(raster_name)
        return failed_layers
    patch_url = f"{raster_url_api}{raster_uuid}/"        
    requests.patch(url=patch_url,json=configuration,headers=json_headers)

def layers_from_atlas_to_lizard(atlas_name,supplier,layer_collection_name,organisation_uuid,failed_layers):
    #Find Atlas UUID
    query_atlas =f"/?domain__contains={atlas_name}" 
    atlas_api = f"https://{atlas_name}.klimaatatlas.net/api/atlases" + query_atlas
    r = requests.get(atlas_api)
    atlas_api_json = r.json()
    atlas_uuid = atlas_api_json["results"][0]["uuid"]

    #Find map layers with that uuid (opletten: werkt wanneer er minder dan 100 lagen in de atlas zitten)
    query_maplayers = f"/?atlas={atlas_uuid}" 
    maplayers_api = f"https://{atlas_name}.klimaatatlas.net/api/maplayers" + query_maplayers
    r = requests.get(maplayers_api)
    maplayers_api_json = r.json()
    maplayer_list = maplayers_api_json["results"]
    layer_collection_url = "https://nens.lizard.net/api/v4/layercollections/"
    for j in range(0,np.size(maplayer_list)):
        maplayer = maplayer_list[j]
        maplayer_url = maplayer["layer_url"]
        maplayer_name = maplayer["wms_layer_name"]
        maplayer_display_name = maplayer["display_name"]
        print(f"Configuring {maplayer_display_name} from the atlas")
        if "geoserver" in maplayer_url:
            print("geoserver laag")
            vector_to_wms(layer_collection_url,layer_collection_name,organisation_uuid,supplier,maplayer)    
        else: 
            print("lizard laag")
            raster_to_layer_collection(layer_collection_url,layer_collection_name,organisation_uuid,supplier,maplayer_name, failed_layers,maplayer_display_name)  
    return failed_layers

#SCRIPT
os.chdir(os.path.dirname(__file__))    
settings = settings_object("atlas2catalogue_v2.ini")

json_headers = {
            "username": settings.username,
            "password": settings.password,
            "Content-Type": "application/json",
        }

failed_layers = []
make_new_layer_collection()
layers_from_atlas_to_lizard(settings.atlas_name,settings.supplier,settings.layer_collection,settings.organisation_uuid,failed_layers)

"""
#DELETE WMS LAGEN wanneer ze opnieuw geconfigureerd moeten worden
y=requests.get("https://nens.lizard.net/api/v4/wmslayers/?layer_collections__slug__icontains=bar_klimaatatlas",headers=json_headers)
result = y.json() 

wms_url = "https://nens.lizard.net/api/v4/wmslayers/"
#uuid_delete = result["results"]["uuid"]
for i in range(np.size(result["results"])):
    uuid =  result["results"][i]["uuid"]
    print(uuid)
    requests.delete(url=f"{wms_url}{uuid}",headers=json_headers) 
"""