# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19 12:01:43 2024

@author: ruben.vanderzaag

Stappen: 
    Voordat je het script draait: 
        1. Zorg dat je rechten krijgt voor de organisatie
        2. Vul het .ini bestandje vullen (dezelfde naam als dit script)
    
    In dit script:
        1. Alle raster en vector lagen in de layer collection worden in een list gezet.
	2. Hetzelfde wordt gedaan voor alle lagen in de klimaatatlas. 
	3. Er wordt gecontroleerd in hoeverre er overlap is in de slugs (beide kanten op).
	4. Als er lagen in de klimaatatlas staan die niet in de layer collection staan, dan krijg je hier een melding van.
	5. De gebruiker kan dan zelf kiezen welke lagen toegevoegd moeten worden aan de layer collection. 
	6. Tenslotte wordt er gecontroleerd of alle lagen goed in de layer collection zijn gezet. 
           
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
    query_raster = f"?name__icontains={raster_name}" 
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

def layers_in_atlas(atlas_name,supplier,layer_collection_name,organisation_uuid,vector_list,raster_list):
    #Find Atlas UUID
    query_atlas =f"/?domain__contains={atlas_name}" 
    atlas_api = f"https://{atlas_name}.klimaatatlas.net/api/atlases" + query_atlas
    r = requests.get(atlas_api)
    atlas_api_json = r.json()
    atlas_uuid = atlas_api_json["results"][0]["uuid"]

    #Find map layers with that uuid (opletten: werkt wanneer er minder dan 200 lagen in de atlas zitten)
    query_maplayers = f"/?atlas={atlas_uuid}" 
    maplayers_api = f"https://{atlas_name}.klimaatatlas.net/api/maplayers" + query_maplayers
    r = requests.get(maplayers_api)
    maplayers_api_json = r.json()
    maplayer_list = maplayers_api_json["results"]
    
    if maplayers_api_json["next"] is not None: 
        r = requests.get(maplayers_api_json["next"])
        maplayers_api_json = r.json()
        maplayer_list.extend(maplayers_api_json["results"])
        
    for j in range(0,np.size(maplayer_list)):
        maplayer_url = maplayer["layer_url"]
        if "geoserver" in maplayer_url: #LET OP: externe wms (gaat dit altijd goed?)
            vector_list.append(maplayer_list[j])
        else: 
            raster_list.append(maplayer_list[j])
                
    return vector_list,raster_list

def layers_in_public_themes_atlas(atlas_name,supplier,layer_collection_name,organisation_uuid,vector_list,raster_list):
    #Find Atlas UUID
    query_atlas =f"/?domain__contains={atlas_name}" 
    atlas_api = f"https://{atlas_name}.klimaatatlas.net/api/atlases" + query_atlas
    r = requests.get(atlas_api)
    atlas_api_json = r.json()
    atlas_uuid = atlas_api_json["results"][0]["uuid"]

    #Find public themes in Atlas
    query_themes =f"/?atlas={atlas_uuid}" 
    themes_api = f"https://{atlas_name}.klimaatatlas.net/api/themes" + query_themes
    r = requests.get(themes_api)
    themes_api_json = r.json()
    themes_list = themes_api_json["results"]
    themes_list_public = []
    maplayers_public = []
    for i in range(0,np.size(themes_list)):
        if themes_list[i]["visibility"]=="public":
            themes_list_public.append(themes_list[i])
            for j in range(0,np.size(themes_list[i]["layers"])):
                maplayers_public.append(themes_list[i]["layers"][j])
    
    maplayer_list = []
    for i in range(0,np.size(maplayers_public)):
        maplayer_uuid = maplayers_public[i]["maplayer_object_uuid"]
        query_maplayers = f"/?uuid={maplayer_uuid}" 
        maplayers_api = f"https://{atlas_name}.klimaatatlas.net/api/maplayers" + query_maplayers
        r = requests.get(maplayers_api)
        maplayers_api_json = r.json()
        maplayer_list.append(maplayers_api_json["results"][0])
        
    for j in range(0,np.size(maplayer_list)):
        maplayer_url = maplayer_list[j]["layer_url"]
        if "geoserver" in maplayer_url: #LET OP: externe wms (gaat dit altijd goed?)
            vector_list.append(maplayer_list[j])
        else: 
            raster_list.append(maplayer_list[j])
    
    return vector_list,raster_list
    

def list_slugs_in_lc(raster,layer_collection_name):
    if raster:
        print("Looking up all rasters in Layer collection")
        url_api= "https://nens.lizard.net/api/v4/rasters/"
    else:
        print("Looking up all wms-layers in layer collection")
        url_api = "https://nens.lizard.net/api/v4/wmslayers/"
    #REMOVE RASSTER EVERYWHERE!!
    query = f"?layer_collections__slug={layer_collection_name}" 
    api = url_api + query
    #print(api)
    r = requests.get(api)
    api_json = r.json()
    list_lc = api_json["results"]
    if api_json["next"] is None:
        next_page = False
    else:
        next_page = True
    while next_page is True:
        api=api_json["next"]
        r = requests.get(api)
        api_json = r.json()
        list_lc.extend(api_json["results"])
        if api_json["next"] is None:
            next_page = False
        else:
            next_page = True
    
    return list_lc 

def compare_atlas_and_lc(list_atlas,list_lc,raster):
    found_layers = []
    not_found_layers =[]
    if raster: 
        function_name = "raster"
    else:
        function_name = "vector"
    
    for i in range(0,np.size(list_atlas)):
        #print(list_atlas[i]["wms_layer_name"])
        try:
            if ":" in list_atlas[i]["wms_layer_name"]:
                atlas_slug = list_atlas[i]["wms_layer_name"].split(":",1)[1]
            else: 
                atlas_slug = list_atlas[i]["wms_layer_name"]
            found = False
            for j in range(0,np.size(list_lc)):
                if raster:
                    slug_lc = list_lc[j]["wms_info"]["layer"]
                else:
                    slug_lc = list_lc[j]["slug"]
                if atlas_slug in slug_lc:
                    found = True
        except:
            print("Slug is waarschijnlijk een NoneType")
            found = False
     
        if found:
            found_layers.append(list_atlas[i])
        else:
            not_found_layers.append(list_atlas[i])

    print(f"{len(found_layers)} {function_name} layers are in layer collection. {len(not_found_layers)} are missing. ")
    print(f"Missing {function_name} layers are: ")
    for i in range(0,np.size(not_found_layers)):
        display_name= not_found_layers[i]["display_name"]
        print(f"{i}. {display_name}") 
    
    return found_layers, not_found_layers

def find_old_layers_in_lc(list_atlas,list_lc,raster):
    found_layers = []
    not_found_layers =[]
    if raster: 
        function_name = "raster"
    else:
        function_name = "vector"
    
    for j in range(0,np.size(list_lc)):
        if raster:
            slug_lc = list_lc[j]["wms_info"]["layer"]
        else:
            slug_lc = list_lc[j]["slug"]
        found = False
        for i in range(0,np.size(list_atlas)):
            if ":" in list_atlas[i]["wms_layer_name"]:
                atlas_slug = list_atlas[i]["wms_layer_name"].split(":",1)[1]
            else: 
                atlas_slug = list_atlas[i]["wms_layer_name"]
            
            if atlas_slug in slug_lc:
                found = True
        
        if found:
            found_layers.append(list_lc[j])
        else:
            not_found_layers.append(list_lc[j])

    print(f"{len(found_layers)} {function_name} layers from the layer collection are also found in the atlas. {len(not_found_layers)} are not. ")
    print(f"Old {function_name} layers are: ")
    for i in range(0,np.size(not_found_layers)):
        display_name= not_found_layers[i]["name"]
        print(f"{i}. {display_name}") 
    
    return found_layers, not_found_layers
    
def missing_wms(atlas_name,supplier,layer_collection_name,organisation_uuid,wms_missing,wms_configured,wms_not_in_layer_collection):
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

    for j in range(0,np.size(maplayer_list)):
        maplayer = maplayer_list[j]
        maplayer_url = maplayer["layer_url"]
        maplayer_name = maplayer["wms_layer_name"]
        if "geoserver" in maplayer_url:
            wms_url = "https://nens.lizard.net/api/v4/wmslayers/"
            query = f"?slug={maplayer_name}"
            get_url = wms_url + query
            y = requests.get(url=get_url,headers=json_headers)
            result = y.json()
            if not result["results"]:
                print(f"The wms-layer {maplayer_name} does not exist yet!")
                wms_missing.append(maplayer_name)
            else: 
                print(f"The wms-layer {maplayer_name} already exists")
                correct_layer_collection = 0
                for x in result["results"]:
                    layer_collection_name = x["layer_collections"][0]["slug"]
                    if layer_collection_name == settings.layer_collection:
                        correct_layer_collection = 1
                        print("Exists and correct layer collection!")
                        wms_configured.append(maplayer_name)
                if correct_layer_collection == 0:
                    print("Exists but wrong layer collection")
                    wms_not_in_layer_collection.append(maplayer_name)

#SCRIPT
os.chdir(os.path.dirname(__file__))    
settings = settings_object("update_catalogue_from_atlas.ini")

json_headers = {
            "username": settings.username,
            "password": settings.password,
            "Content-Type": "application/json",
        }

# Find new maplayers in Atlas, which are not yet in the layer collection
vector_list_atlas=[]
raster_list_atlas = []
raster_list_lc=[]
vector_list_lc = []
vector_found_layers=[]
vector_not_found_layers = []
raster_found_layers=[]
raster_not_found_layers =[]
vector_lc_found_layers=[]
vector_lc_not_found_layers = []
raster_lc_found_layers=[]
raster_lc_not_found_layers =[]
vector_to_add =[]
raster_to_add =[]
failed_layers = []
layer_collection_url = "https://nens.lizard.net/api/v4/layercollections/"

# Finding raster and vector layers currently in klimaatatlas (public themes only):
#vector_list_atlas,raster_list_atlas = layers_in_atlas(settings.atlas_name,settings.supplier,settings.layer_collection,settings.organisation_uuid, vector_list_atlas,raster_list_atlas)
vector_list_atlas,raster_list_atlas = layers_in_public_themes_atlas(settings.atlas_name,settings.supplier,settings.layer_collection,settings.organisation_uuid, vector_list_atlas,raster_list_atlas) 

# Finding raster and vector layers currently in layer collection:
raster_list_lc = list_slugs_in_lc(True,settings.layer_collection)
vector_list_lc = list_slugs_in_lc(False,settings.layer_collection)
"""
# Find out which layers in the layer collection are not configured in public themes in the Atlas
vector_lc_found_layers, vector_lc_not_found_layers=find_old_layers_in_lc(vector_list_atlas,vector_list_lc,False)
raster_lc_found_layers, raster_lc_not_found_layers=find_old_layers_in_lc(raster_list_atlas,raster_list_lc,True)
"""
# Compare the lists to find missing slugs and prompt user for input
vector_found_layers, vector_not_found_layers = compare_atlas_and_lc(vector_list_atlas,vector_list_lc,False)
user_input_vector = input("Which vector layers would you like to add to the layer collection? Enter numbers separated by commas.")
user_list_vector = user_input_vector.split(',')
user_list_vector = [int(index.strip()) for index in user_list_vector if index.strip().isdigit()]
for i in range(0,np.size(user_list_vector)):
    vector_to_add.append(vector_not_found_layers[user_list_vector[i]])

raster_found_layers, raster_not_found_layers = compare_atlas_and_lc(raster_list_atlas,raster_list_lc,True)
user_input_raster = input("Which raster layers would you like to add to the layer collection? Enter numbers separated by commas.")
user_list_raster = user_input_raster.split(',')
user_list_raster = [int(index.strip()) for index in user_list_raster if index.strip().isdigit()]
for i in range(0,np.size(user_list_raster)):
    raster_to_add.append(raster_not_found_layers[user_list_raster[i]])
 
# Add the selected layers to the layer collection
for i in range(0,np.size(raster_to_add)):
    maplayer_name = raster_to_add[i]["wms_layer_name"]
    maplayer_display_name = raster_to_add[i]["display_name"]
    raster_to_layer_collection(layer_collection_url,settings.layer_collection,settings.organisation_uuid,settings.supplier,maplayer_name,failed_layers,maplayer_display_name)    

for i in range(0,np.size(vector_to_add)):
    maplayer = vector_to_add[i]
    vector_to_wms(layer_collection_url,settings.layer_collection,settings.organisation_uuid,settings.supplier,maplayer)


#missende WMS-lagen opsporen
wms_missing =[]
wms_configured=[]
wms_not_in_layer_collection=[]                
missing_wms(settings.atlas_name,settings.supplier,settings.layer_collection,settings.organisation_uuid,wms_missing,wms_configured,wms_not_in_layer_collection)        


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