# Documentation https://demo.lizard.net/doc/api.html#post--api-v3-rasters-

# system imports
import os

# Third-party imports
import json
import math
import multiprocessing as mp
from requests import get, post, codes, delete, put, patch
from catalogue.credentials import USERNAME, PASSWORD

# globals
CONFIG = {
    "name": "",
    "observation_type": "",
    "description": "",
    "supplier": "",
    "supplier_code": "",
    "aggregation_type": 2,
    "options": "",
    "access_modifier": 0,
    "rescalable": "",
    "organisation": "",
    "datasets": [""],
    "slug": "",
}


class StoreNotFound(Exception):
    pass


class SlugNotFound(Exception):
    pass


class rasterstore(object):
    def __init__(
        self,
        uuid=None,
        username=USERNAME,
        password=PASSWORD,
        update_slugs=False,
    ):

        self.username = username
        self.password = password
        self.raster_url = "https://demo.lizard.net/api/v4/rasters/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"

        self.headers = {"username": username, "password": password}
        self.json_headers = dict(
            self.headers, **{"Content-Type": "application/json"}
        )

        if uuid:
            self.uuid = uuid
            self.raster_uuid_url = self.raster_url + self.uuid + "/"
            self.config = self.get_store(self.uuid)

        if update_slugs:
            path = os.path.dirname(os.path.realpath(__file__))
            self.slug_dict = load_slug_dict(
                self.raster_url, self.headers, path
            )

    def get_call(self, params, url=None, headers=None):
        if not url:
            url = self.raster_url

        if not headers:
            headers = self.headers

        return get_call_or(params, url, headers)

    def get_store(self, uuid):
        try:
            return self.get_call({"uuid": uuid})["results"][0]
        except Exception as e:
            raise StoreNotFound(uuid, e)

    def get_uuid_by_slug(self, slug):
        if "," in slug:
            print("Found", slug.split(","), "as a slug, chose the second")
            slug = slug.split(",")[1]
        return list(self.slug_dict.keys())[
            list(self.slug_dict.values()).index(slug)
        ]

    def get_organisation_uuid(self, organisation):
        r = self.get_call(
            {"name__icontains": organisation}, self.organisation_url,
        )
        self.organisation_uuid = r.json()["results"][0]["uuid"]
        return r.json()["results"][0]

    def last_modified_raster_search(self, page, page_size=50):
        return self.get_call(
            {
                "ordering": "-last_modified",
                "page": str(page),
                "page_size": str(page_size),
            }
        )

    def organisation_search(self, page, organisation, page_size=50):
        return self.get_call(
            {
                "organisation_uuid": str(organisation),
                "page": str(page),
                "page_size": str(page_size),
            }
        )

    def dataset_search(self, page, dataset, page_size=50):
        return self.get_call(
            {
                "datasets__slug": dataset,
                "page": str(page),
                "page_size": str(page_size),
            }
        )

    def get_slug(self, config):
        if "slug" in config:
            slug = config["slug"]
        else:
            slug = config["wms_info"]["layer"]
        return slug

    def reset_config(self, config):
        if "id" in config:
            del config["id"]
        if isinstance(config["observation_type"], dict):
            config["observation_type"] = config["observation_type"]["code"]
        return config

    def overwrite_store(self, config):
        """ overwrites store based on uuid if given, else on slug"""
        if "uuid" in config:
            self.delete_store(config["uuid"])
            return self.reset_config(config)

        slug = self.get_slug(config)
        if config["datasets"]:
            dataset_available = len(config["datasets"]) > 0
        else:
            dataset_available = False

        if dataset_available:
            store = self.get_raster_by_dataset(config["datasets"][0], slug)

        if not dataset_available or not store:
            store = self.get_raster_by_slug(slug)

        if store:
            self.delete_store(store["uuid"])
            return self.reset_config(config)
        else:
            print(
                "Overwrite True but store does not exist or could not"
                " be found"
            )
            return None

    def delete_store(self, uuid):
        r = delete(url=self.raster_url + uuid + "/", headers=self.headers)
        if r.status_code == 204:
            print("delete store succes", r.status_code)
        else:
            print("delete store failure:", r.json())

    def create(self, config, overwrite=False):
        if overwrite:
            new_config = self.overwrite_store(config)
            if new_config:
                config = new_config

        r = post(
            url=self.raster_url,
            data=json.dumps(config),
            headers=self.json_headers,
        )

        if r.status_code == 201:
            self.raster_uuid = r.json()["uuid"]
            print("create store succes", r.status_code)
            return r.json()
        else:
            print("create store failure", r.status_code)
            print(r.json())
            raise ValueError("create store failure", r.json())

    def post(self, path, post_only=False, config=False):

        if post_only:
            raster = self.get_raster_by_slug(config["slug"])
            self.raster_uuid = raster["uuid"]

        print(path)
        url = self.raster_url + self.raster_uuid + "/data/"

        r = post(
            url=url, files={"file": open(path, "rb")}, headers=self.headers
        )

        if not r.status_code == codes.ok:
            print("post data failure", r.status_code)
            print(r.json())

        else:
            print("post data succes", r.status_code)

    def put_data(self, config):
        r = put(
            url=self.raster_url, data=json.dumps(config), headers=self.headers,
        )

        if not r.status_code == codes.ok:
            print("put data failure", r.status_code)
            print(r.json())

        else:
            print("put data succes", r.status_code)

    def update(self, config):
        r = patch(
            url=self.raster_url, data=json.dumps(config), headers=self.headers,
        )

        if not r.status_code == codes.ok:
            print("patch data failure", r.status_code)
            print(r.json())

        else:
            print("patch data succes", r.status_code)

    def get_zonal(self, wkt, stat, size, proj="EPSG:28992"):
        return self.get_call(
            url=self.raster_uuid_url + "zonal/",
            params={
                "geom": wkt,
                "zonal_statistic": stat,
                "pixel_size": size,
                "zonal_projection": proj,
            },
        )

    def get_counts(self, wkt, style):
        return self.get_call(
            url=self.raster_uuid_url + "counts/",
            params={"geom": wkt, "style": style, "limit": 100000},
        )

    def atlas2store(
        self, atlas_json, supplier, rescalable=False, acces_modifier=0
    ):
        raster = atlas_json["rasterstore"]
        atlas = atlas_json["atlas"]

        self.configuration = {
            "name": atlas["name"],
            "description": strip_information(atlas["information"]),
            "supplier": supplier,
            "supplier_code": raster["name"],
            "aggregation_type": 2,
            "options": raster["options"],
            "access_modifier": acces_modifier,
            "rescalable": rescalable,
            "source": raster["source"]
            #  "source":
        }

        try:
            code = raster["observation_type"]["code"]

        except TypeError:
            code = "-"

        try:
            org_uuid = raster["organisation"]["uuid"]

        except TypeError:
            print("Uuid of organisation not filled, using nens")
            org_uuid = "61f5a464-c350-44c1-9bc7-d4b42d7f58cb"

        self.configuration.update({"observation_type": code})
        self.configuration.update({"organisation": org_uuid})


def mp_slug_search(raster_url, headers, page, pages, page_size):

    print("Adding page", page, "of", pages)
    r = get_call_or(
        {"page_size": page_size, "page": page, "ordering": "-last_modified"},
        raster_url,
        headers,
    )
    slug_dict = {}
    for result in r["results"]:
        slug_dict[result["uuid"]] = result["wms_info"]["layer"]

    return slug_dict


def get_call_or(params, url, headers):
    query = {"url": url, "headers": headers, "params": params}
    r = get(**query)
    print(r.url)
    if r.status_code == 200:
        return r.json()
    else:
        return ValueError(
            "Call failed with query:",
            "url",
            query["url"],
            "params",
            query["params"],
            "json:",
            r.json(),
        )


def load_slug_dict(raster_url, headers, path):

    slug_dict_path = os.path.join(path, "data/slug_dict.json")
    if not os.path.exists(slug_dict_path):
        print("Did not find slug_dict.json, creating new and starting update")

        r = get_call_or({"page_size": 1}, url=raster_url, headers=headers)

        page_size = 100
        pages = math.ceil(r["count"] / page_size)
        args = [
            (raster_url, headers, p, pages, page_size) for p in range(1, pages)
        ]

        slug_dict = {}
        with mp.Pool(processes=10) as pool:
            for result_dict in pool.starmap(mp_slug_search, args):
                slug_dict.update(result_dict)

        with open(slug_dict_path, "w") as fp:
            json.dump(slug_dict, fp)
            return slug_dict

    else:
        with open(slug_dict_path) as json_file:
            return json.load(json_file)


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


def create_config(
    name,
    slug,
    observation_type,
    description,
    style,
    organisation,
    supplier,
    datasets=None,
    access_modifier=0,
    aggregation_type=2,
):

    config = {}
    config["name"] = name
    config["slug"] = slug
    config["observation_type"] = observation_type
    config["description"] = description
    config["supplier"] = supplier
    config["supplier_code"] = slug.replace(":", "_")
    config["aggregation_type"] = aggregation_type
    config["options"] = {"styles": style}
    config["organisation"] = organisation
    config["datasets"] = [datasets]
    config["access_modifier"] = access_modifier
    config["rescalable"] = 0
    return config


if __name__ == "__main__":
    os.chdir("C:/Users/chris.kerklaan/Documents/temp")
