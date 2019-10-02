# Documentation https://demo.lizard.net/doc/api.html#post--api-v3-rasters-


# System imports
import sys

sys.path.append("C:/Users/chris.kerklaan/Documents/base_modules")

# Third-party imports
import json
from requests import get, post, codes, delete

# Local imports
from lizard.localsecret import username, password


class rasterstore(object):
    def __init__(self, username=username, password=password):
        self.username = username
        self.password = password
        self.raster_url = "https://demo.lizard.net/api/v4/rasters/"
        self.raster_uuid = "https://demo.lizard.net/api/v4/rasters/{uuid}/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"

        self.get_headers = {
            "username": username,
            "password": password,
            "Content-Type": "application/json",
        }
        self.post_headers = {"username": username,
                             "password": password}

    def get_nens_id(self):
        r = get(
            url=self.organisation_url,
            headers=self.post_headers,
            params={"name__icontains": "nelen"},
        )
        self.organisation_uuid = r.json()["results"][0]["uuid"]
        return self.organisation_uuid

    def get_store(self, slug):
        name = slug.split(":")[1]

        r = get(
            url=self.raster_url,
            headers=self.post_headers,
            params={"name__icontains": name},
        )

        results_exists = r.json()["count"] > 0
        slug_exists = False
        slug_result = None

        if results_exists:
            for result in r.json()["results"]:
                layer_wms = result["wms_info"]["layer"]
                if layer_wms == slug:
                    return result, True

        return slug_result, slug_exists

    def delete_store(self, uuid):
        
        r = delete(
            url=self.raster_uuid.format(uuid = uuid),
            headers=self.get_headers
        )
        if r.status_code == 204:
            print('delete store succes', r.status_code)
        else:
            print("delete store failure:", r.json())
        

    def create(self, configuration, overwrite=False):
        _json, store_exists = self.get_store("nelen-schuurmans:" +
                                             configuration['name'])

        if not store_exists:
            configuration["organisation"] = self.organisation_uuid
            r = post(
                url=self.raster_url,
                data=json.dumps(configuration),
                headers=self.get_headers,
            )

            if not r.status_code == 201 or not r.status_code == 201:
                print("create store failure", r.status_code)
                print(r.json())

            else:
                self.raster_uuid = r.json()["uuid"]
                print("create store succes", r.status_code)
                return r.json()["wms_info"]

        else:
            self.raster_uuid = _json["uuid"]
            print(
                "rasterstore already exists, overwrite is false,"
                "thus using existing store"
            )
            return _json["wms_info"]

    def post_data(self, path):
        print(path)
        url = self.raster_url + self.raster_uuid + "/data/"

        r = post(
            url=url,
            files={"file": open(path, "rb")},
            headers=self.post_headers,
        )

        if not r.status_code == codes.ok:
            print("post data failure", r.status_code)
            print(r.json())

        else:
            print("post data succes", r.status_code)

if __name__ == "__main__":
    pass
