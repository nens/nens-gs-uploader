# Documentation https://demo.lizard.net/doc/api.html#post--api-v3-rasters-


# System imports
# import sys
# sys.path.append("C:/Users/chris.kerklaan/tools/")

# Third-party imports
import json
from requests import get, post, codes, delete, put
from tqdm import tqdm

# Local imports
from nens_gs_uploader.localsecret.localsecret import username, password


class rasterstore(object):
    def __init__(self, username=username, password=password):
        self.username = username
        self.password = password
        self.raster_url = "https://demo.lizard.net/api/v4/rasters/"
        self.search_url = "https://demo.lizard.net/api/v4/search/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"

        self.post_headers = {
            "username": username,
            "password": password,
            "Content-Type": "application/json",
        }
        self.get_headers = {"username": username, "password": password}

    def get_organisation_uuid(self, organisation):
        r = get(
            url=self.organisation_url,
            headers=self.get_headers,
            params={"name__icontains": organisation},
        )
        self.organisation_uuid = r.json()["results"][0]["uuid"]
        return r.json()["results"][0]

    def last_modified_raster_search(self, page, page_size=50):
        r = get(
            url=self.raster_url
            + "?ordering=-last_modified&page={}&page_size={}".format(
                str(page), str(page_size)
            ),
            headers=self.get_headers,
        )
        if r.status_code == 200:
            return r.json()["results"]
        else:
            return ValueError("Get Last modified failure")

    def organisation_search(self, page, organisation, page_size=50):
        r = get(
            url=self.raster_url
            + "?organisation__uuid={}&page={}&page_size={}".format(
                str(organisation), str(page), str(page_size)
            ),
            headers=self.get_headers,
        )
        if r.status_code == 200:
            return r.json()["results"]
        else:
            return None

    def dataset_search(self, page, dataset, page_size=50):
        r = get(
            url=self.raster_url
            + "?datasets__slug={}&page={}&page_size={}".format(
                str(dataset), str(page), str(page_size)
            ),
            headers=self.get_headers,
        )
        if r.status_code == 200:
            return r.json()["results"]
        else:
            return None

    def match_results_to_slug(self, results, slug):
        for raster in results:
            if slug == raster["wms_info"]["layer"]:
                return raster
            else:
                pass

        return None

    def get_raster_by_slug(
        self, slug, search="last_modified", organisation=None, pages=10
    ):

        print("Searching {} pages".format(pages))
        for page in tqdm(range(1, pages + 1)):
            if search == "last_modified":
                results = self.last_modified_raster_search(page)
                result = self.match_results_to_slug(results, slug)
                if result is not None:
                    return result

            elif search == "organisation":
                results = self.organisation_search(page, organisation, page_size=1000)
                result = self.match_results_to_slug(results, slug)
                if result is not None:
                    return result
            else:
                pass
        return None

    def get_raster_by_dataset(self, dataset_slug, raster_slug, pages=10):
        for page in tqdm(range(1, pages + 1)):
            results = self.dataset_search(page, dataset_slug)
            result = self.match_results_to_slug(results, raster_slug)
            if result is not None:
                return result, True

        return None, False

    def get_store(self, search_terms, slug, method="search", uuid=None):
        if method == "search":
            search_terms_new = []
            for term in search_terms:
                search_terms_new.append(term)
                search_terms_new.append(term.upper())
                search_terms_new.append(term.lower())

            search_terms = list(set(search_terms_new + [slug] + slug.split(":")))
            # print("search terms..", search_terms)

            for search_term in list(set(search_terms)):
                # print("search name...",search_term )
                r = get(
                    url=self.raster_url,
                    headers=self.get_headers,
                    params={"name__icontains": search_term},
                )

                if r.json()["count"] > 0:
                    for result in r.json()["results"]:
                        layer_wms = result["wms_info"]["layer"]
                        if layer_wms == slug:
                            return result, True

            search_organisations = slug.split(":")
            for organisation in search_organisations:
                # print("search organisation...",search_term )
                r = get(
                    url=self.raster_url,
                    headers=self.get_headers,
                    params={"?organisation__name__icontains": organisation},
                )

                if r.json()["count"] > 0:
                    for result in r.json()["results"]:
                        layer_wms = result["wms_info"]["layer"]
                        if layer_wms == slug:
                            return result, True
            return None, False

        else:
            r = get(url=self.raster_url + uuid + "/", headers=self.get_headers)
            if r.status_code == 200:
                layer_wms = r.json()["wms_info"]["layer"]
                if layer_wms == slug:
                    return r.json(), True
                else:
                    return r.json(), False
            else:
                print("get store failure", r.status_code)
                print(r.json())
                raise ValueError("get store failure")

            return None, False

    def delete_store(self, uuid):

        r = delete(url=self.raster_url + uuid + "/", headers=self.get_headers)
        if r.status_code == 204:
            print("delete store succes", r.status_code)
        else:
            print("delete store failure:", r.json())

    def create(self, configuration, overwrite=False):
        if overwrite:
            if isinstance(configuration["datasets"], object):
                raster, raster_found = self.get_raster_by_dataset(
                    configuration["datasets"][0], configuration["slug"]
                )

            if not raster_found:
                raster = self.get_raster_by_slug(configuration["slug"])

            if raster_found:
                self.delete_store(raster["uuid"])
            else:
                print("Overwrite true but store does not exist")

        r = post(
            url=self.raster_url,
            data=json.dumps(configuration),
            headers=self.post_headers,
        )

        if r.status_code == 201:
            self.raster_uuid = r.json()["uuid"]
            print("create store succes", r.status_code)
            return r.json()["wms_info"]
        else:
            print("create store failure", r.status_code)
            print(r.json())
            raise ValueError("create store failure")

    def post_data(self, path, post_only=False, configuration=False):

        if post_only:
            raster = self.get_raster_by_slug(configuration["slug"])
            self.raster_uuid = raster["uuid"]

        print(path)
        url = self.raster_url + self.raster_uuid + "/data/"

        r = post(url=url, files={"file": open(path, "rb")}, headers=self.get_headers)

        if not r.status_code == codes.ok:
            print("post data failure", r.status_code)
            print(r.json())

        else:
            print("post data succes", r.status_code)

    def put_data(self, configuration):
        r = put(
            url=self.raster_url,
            data=json.dumps(configuration),
            headers=self.get_headers,
        )

        if not r.status_code == codes.ok:
            print("put data failure", r.status_code)
            print(r.json())

        else:
            print("put data succes", r.status_code)

    def atlas2store(self, atlas_json, supplier, rescalable=False, acces_modifier=0):
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
