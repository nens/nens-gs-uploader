# -*- coding: utf-8 -*-
"""#
Created on Mon Jul 22 21:39:39 2019

@author: chris.kerklaan - N&S
"""

# Third-party imports
import requests
import os
import re
from bs4 import BeautifulSoup as bs
from geoserver.catalog import Catalog
from geoserver.util import shapefile_and_friends
from tqdm import tqdm
from core.credentials import username, password

REST = {
    "STAGING": "https://maps2.staging.lizard.net/geoserver/rest/",
    "PRODUCTIE_KLIMAATATLAS": "https://maps1.klimaatatlas.net/geoserver/rest/",
    "PRODUCTIE_FLOODING": "https://flod-geoserver1.lizard.net/geoserver/rest/",
    "PRODUCTIE_LIZARD": "https://geoserver9.lizard.net/geoserver/rest/",
    "PROJECTEN_KLIMAATATLAS": "https://maps1.project.lizard.net/geoserver/rest/",
    "PROJECTEN_LIZARD": "https://maps1.project.lizard.net/geoserver/rest/",
}
SERVERS = {
    "STAGING": "https://maps2.staging.lizard.net/geoserver/",
    "PRODUCTIE_KLIMAATATLAS": "https://maps1.klimaatatlas.net/geoserver/",
    "PRODUCTIE_FLOODING": "https://flod-geoserver1.lizard.net/geoserver/",
    "PRODUCTIE_LIZARD": "https://geoserver9.lizard.net/geoserver/",
    "PROJECTEN_KLIMAATATLAS": "https://maps1.project.lizard.net/geoserver/",
    "PROJECTEN_LIZARD": "https://maps1.project.lizard.net/geoserver/",
}


class wrap_geoserver:
    """ Geoserver (gsconfig) wrapper """

    def __init__(
        self, geoserver_name, username=username, password=password, easy=False
    ):
        if geoserver_name in list(REST.keys()):
            self.path = REST[geoserver_name]
        else:
            self.path = geoserver_name
        self.wms = self.path.replace("rest/", "wms")

        self.name = geoserver_name
        self.catalog = Catalog(self.path, username, password)

        if not easy:
            self.layers = []
            self.layer_names = []

            for layer in self.catalog.get_layers():
                self.layers.append(layer)
                self.layer_names.append(layer.name)

            self.stores = [store for store in self.catalog.get_stores()]
            self.store_names = [store.name for store in self.stores]

            styles = []
            self.workspaces = []
            self.workspace_names = []

            for workspace in self.catalog.get_workspaces():
                styles = styles + self.catalog.get_styles(workspace)
                self.workspace_names.append(workspace._name)
                self.workspaces.append(workspace)

            self.styles = styles + [style for style in self.catalog.get_styles()]
            self.style_names = [style.name for style in self.styles]

    def unpack(self, workspace_name, store_type="datastore"):
        layers_and_styles = {}
        features = []
        workspace = self.get_workspace(workspace_name)

        if store_type == "datastore":
            store_url = workspace.datastore_url
        elif store_type == "coveragestore":
            store_url = workspace.coveragestore_url
        else:
            print("No correct store given")

        for datastore in tqdm(get(store_url, "name")):
            url = "{}workspaces/{}/datastores/{}".format(
                self.path, workspace.name, datastore
            )
            features = features + get(url, between_quotes=True)

        for feature in features:
            layer_name = os.path.basename(feature).split(".")[0]
            self.get_layer(self.get_slug(workspace.name, layer_name))
            layers_and_styles[layer_name] = self.layer.default_style

        setattr(self, workspace_name + "_data", layers_and_styles)
        return layers_and_styles

    def get_layer(self, layer, easy=False):
        self.layer = self.catalog.get_layer(layer)

        if not easy:
            self.resource = self.layer.resource
            self.layer_name = self.layer.resource.name
            self.sld_name = self.layer.default_style.name
            self.sld_body = self.layer.default_style.sld_body
            self.layer_latlon_bbox = self.layer.resource.latlon_bbox
            self.layer_title = self.layer.resource.title
            self.layer_abstract = self.layer.resource.abstract

    def get_store(self, layer):
        self.store = self.layer.resource._store

    def get_resource(self):
        self.resource = self.catalog.get_resource(self.layer.name, self.store)

    def get_workspace(self, workspace_name):
        self.workspace = self.catalog.get_workspace(workspace_name)
        self.workspace_name = self.workspace._name
        return self.workspace

    def write_abstract(self, data, load_resource=True):
        if load_resource:
            self.get_resource()
        self.resource.abstract = data
        self.catalog.save(self.resource)

    def write_title(self, title):
        self.resource.title = title
        self.catalog.save(self.resource)

    def get_connection_parameters(self):
        self.get_resource()
        return self.resource.store.connection_parameters

    def create_workspace(self, workspace_name):
        workspace_exists = workspace_name in self.workspace_names

        if not workspace_exists:
            self.workspace = self.catalog.create_workspace(workspace_name)

        else:
            print("workspace already exists, using existing workspace")

        self.workspace = self.catalog.get_workspace(workspace_name)
        self.workspace_name = workspace_name

    def create_postgis_datastore(self, store_name, workspace_name, pg_data):

        try:
            self.store = self.catalog.get_store(store_name, self.workspace_name)
            print("store within workspace exists, using existing store")

        except Exception as e:
            print(e)

            ds = self.catalog.create_datastore(store_name, workspace_name)
            ds.connection_parameters.update(
                host=pg_data["host"],
                port=pg_data["port"],
                database=pg_data["database"],
                user=pg_data["username"],
                passwd=pg_data["password"],
                dbtype="postgis",
                schema="public",
            )

            self.save(ds)
            self.store = self.catalog.get_store(store_name, self.workspace_name)
            self.store_name = store_name

    def publish_layer(
        self, layer_name, workspace_name, overwrite=False, epsg="3857", reload=False
    ):

        layer_exists = layer_name in self.layer_names
        # if layer_name in self.workspace_layers[workspace_name]:
        slug = self.get_slug(workspace_name, layer_name)
        if overwrite and layer_exists:
            print("Layer exists, deleting layer")
            try:

                self.layer = self.catalog.get_layer(slug)
                self.delete(self.layer)
                self.reload()

                layer_exists = False

            except Exception as e:
                print(e)
                print("Layer does not exist in workspace")
                layer_exists = False

        if not layer_exists:

            feature_type = self.catalog.publish_featuretype(
                layer_name,
                self.store,
                "EPSG:{}".format(str(epsg)),
                srs="EPSG:{}".format(str(epsg)),
            )
            self.save(feature_type)
            self.feature_type = feature_type

        else:
            print("layer already exists, using existing layer")

        if reload:
            self.get_layer(slug)

        self.layer_name = layer_name

    def publish_layergroup(self, name, layers, styles=(), bounds=None, workspace=None):
        layer_group = self.catalog.create_layergroup(
            name, layers, styles, bounds, workspace
        )
        self.save(layer_group)

    def save(self, save_object):
        return self.catalog.save(save_object)

    def close(self):
        self.catalog = None

    def delete(self, delete_object):
        self.catalog.delete(delete_object)

    def reload(self):
        self.catalog.reload()

    def upload_shapefile(self, layer_name, shapefile_path):
        path = shapefile_path.split(".shp")[0]
        shapefile = shapefile_and_friends(path)
        ft = self.catalog.create_featurestore(layer_name, shapefile, self.workspace)
        self.save(ft)

    def upload_sld(self, sld_name, workspace_name, sld, overwrite=True):
        style_exists = sld_name in self.style_names

        if overwrite and style_exists:
            print("Overwriting style")
            style = self.catalog.get_style(sld_name, workspace_name)
            self.delete(style)
            self.reload()
            style_exists = False
            
        if not style_exists:
            try:
                self.catalog.create_style(sld_name, sld, False, workspace_name, "sld11")
            except Exception as e:
                print(e)

                style = self.catalog.get_style(sld_name, workspace_name)
                self.delete(style)
                self.reload()
                self.catalog.create_style(sld_name, sld, False, workspace_name, "sld10")
            self.style_name = sld_name

        else:
            if style_exists:
                print("Style already exists, using current style")
                self.style_name = sld_name

    def set_sld_for_layer(self, workspace_name=None, style_name=None, use_custom=False):
        if not use_custom:
            workspace_name = self.workspace_name
            style_name = self.style_name
            self.style_slug = self.get_slug(workspace_name, style_name)

        else:
            if workspace_name is None:
                self.style_slug = style_name
            else:
                self.style_slug = self.get_slug(workspace_name, style_name)

        self.style = self.catalog.get_style(self.style_slug)

        print("Setting {} for {}".format(self.style.name, self.layer.name))
        self.layer.default_style = self.style
        self.save(self.layer)

    def get_slug(self, workspace, name):
        return "{}:{}".format(workspace, name)

    def get_slug_data(self, slug):
        workspace_name = slug.split(":")[0]
        layer_name = slug.split(":")[1]
        return workspace_name, layer_name

    def get_sld(self, layer_slug=None):
        if layer_slug is None:
            self.style = self.catalog.get_style(self.layer_slug)
        else:
            self.style = self.catalog.get_style(layer_slug)

        self.sld_body = self.style.sld_body
        return self.sld_body

    def get_layer_workspace(self, layer_name):
        return self.catalog.get_layer(layer_name).resource.workspace.name


def get(url, _type="a", between_quotes=False):
    r = requests.get(url)
    soup = bs(r.content, "html.parser")
    _list = []
    for i in soup.find_all(_type):
        i = str(i)
        if between_quotes:
            _list = _list + re.findall('"([^"]*)"', i)
        else:
            name = i.split("<{}>".format(_type))[-1]
            name = name.split("</{}>".format(_type))[0]
            _list.append(name)

    return _list


if __name__ == "__main__":
    #    fl = wrap_geoserver("PRODUCTIE_FLOODING")
    #    ka = wrap_geoserver("PRODUCTIE_KLIMAATATLAS")
    #    ka.write_title
    pass
