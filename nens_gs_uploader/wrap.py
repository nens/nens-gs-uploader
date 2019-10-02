# -*- coding: utf-8 -*-
"""#
Created on Mon Jul 22 21:39:39 2019

@author: chris.kerklaan - N&S
"""

# Third-party imports
import csv
from geoserver.catalog import Catalog
from geoserver.util import shapefile_and_friends
from tqdm import tqdm

# local imports
from nens_gs_uploader.localsecret.localsecret import username, password
from nens_gs_uploader.postgis import SERVERS


class wrap_geoserver:
    """ Geoserver (gsconfig) wrapper """

    def __init__(self, geoserver_name, username=username, password=password):
        self.name = geoserver_name
        self.path = SERVERS[geoserver_name]
        self.catalog = Catalog(self.path, username, password)

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

    def unpack(self, workspace):
        """ Fetches all data in specific workspace. """
        """ Does not unpack coverage stores """

        layers_in_workspace = []
        with open("hrefs.csv", "r") as csvfile:
            read = csv.reader(csvfile, delimiter=",")
            for row in read:
                if row[1] == "None" or "datastore" not in row[1]:
                    continue

                splits = row[1].split("workspaces/")[1].split("/")
                if workspace == splits[0]:
                    layers_in_workspace.append(splits[-1].split(".xml")[0])

        self.data = {}
        for layer_name in tqdm(layers_in_workspace):

            try:
                layer = self.catalog.get_layer(layer_name)
                style = layer.default_style
                print(style.name)
                # resource = layer.resource
                layer_data = {
                    #        "layer"     : layer,
                    "style": style,
                    #        "resource"  : resource,
                    #        "connection": layer.resource.store.connection_parameters,
                    #       "store"     : resource.store
                }

                self.data[layer_name] = layer_data

            except Exception:
                pass

        return self.data

    def get_layer(self, layer):
        self.layer = self.catalog.get_layer(layer)
        self.resource = self.layer.resource
        self.layer_name = self.layer.resource.name
        self.sld_name = self.layer.default_style.name

    def get_store(self, layer):
        self.store = self.layer.resource._store

    def get_resource(self):
        self.resource = self.catalog.get_resource(self.layer.name, self.store)

    def get_workspace(self, workspace_name):
        self.workspace = self.catalog.get_workspace(workspace_name)
        self.workspace_name = self.workspace._name

    def write_abstract(self, data):
        self.resource.abstract = data
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
            self.store = self.catalog.get_store(
                store_name, self.workspace_name
            )
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
            self.store = self.catalog.get_store(
                store_name, self.workspace_name
            )
            self.store_name = store_name

    def publish_layer(self, layer_name, overwrite=False, epsg="3857"):
        layer_exists = layer_name in self.layer_names

        if overwrite and layer_exists:
            print("layer already exists, overwriting layer")

            self.layer = self.catalog.get_layer(layer_name)
            self.delete(self.layer)
            self.reload()

            layer_exists = False

        if not layer_exists:
            feature_type = self.catalog.publish_featuretype(
                layer_name,
                self.store,
                "EPSG:{}".format(epsg),
                srs="EPSG:{}".format(epsg),
            )
            self.save(feature_type)
            self.feature_type = feature_type

        else:
            print("layer already exists, using existing layer")

        self.get_layer(layer_name)
        self.layer_name = layer_name

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
        ft = self.catalog.create_featurestore(
            layer_name, shapefile, self.workspace
        )
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
                self.catalog.create_style(
                    sld_name, sld, False, workspace_name, "sld11"
                )
            except Exception as e:
                print(e)

                style = self.catalog.get_style(sld_name, workspace_name)
                self.delete(style)
                self.reload()
                self.catalog.create_style(
                    sld_name, sld, False, workspace_name, "sld10"
                )
            self.style_name = sld_name

        else:
            if style_exists:
                print("Style already exists, using current style")
                self.style_name = sld_name

    def set_sld_for_layer(self):
        self.style_slug = self.get_slug(self.workspace_name, self.style_name)
        self.style = self.catalog.get_style(self.style_slug)
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


if __name__ == "__main__":
    pass
