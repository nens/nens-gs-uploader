# Documentation https://demo.lizard.net/doc/api.html#post--api-v3-rasters-

# system imports
import os

# Third-party imports
import json
import math
import multiprocessing as mp
from requests import get, post, codes, delete, put, patch
from core.credentials import username
from core.credentials import password
from core.project import mk_dir


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
        self, uuid=None, username=username, password=password, 
    ):

        self.username = username
        self.password = password
        self.raster_url = "https://demo.lizard.net/api/v4/rasters/"
        self.raster_v3_url = "https://demo.lizard.net/api/v3/rasters/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"
        self.sources_url = "https://demo.lizard.net/api/v4/rastersources/"
        self.headers = {"username": username, "password": password}
        self.json_headers = dict(self.headers, **{"Content-Type": "application/json"})

        if uuid:
            self.uuid = uuid
            self.raster_uuid_url = self.raster_url + self.uuid + "/"
            self.config = self.get_store(self.uuid)

        path = os.path.dirname(os.path.realpath(__file__))
        self.slug_dict = load_slug_dict(self.raster_url, 
                                        self.headers, 
                                        path,
                                        update=False)

    def get_call(self, params, url=None, headers=None):
        if not url:
            url = self.raster_url

        if not headers:
            headers = self.headers

        return get_call_or(params, url, headers)
    
    def post_call(self, params, url=None, headers=None):
        if not url:
            url = self.raster_url
        
        if not headers:
             headers = self.json_headers
        
        return post_call_or(params, url, headers)    
    

    def get_store(self, uuid):
        try:
            return self.get_call({"uuid": uuid})["results"][0]
        except Exception as e:
            raise StoreNotFound(uuid, e)

    def last_modified_raster_search(self, page, page_size=50):
        return self.get_call({"ordering": "-last_modified", 
                      "page": str(page),
                      "page_size": str(page_size)})
        
    def organisation_search(self, page, organisation, page_size=50):
        return self.get_call({"organisation_uuid":str(organisation),
                      "page": str(page),
                      "page_size": str(page_size)})
    
    def dataset_search(self, page, dataset, page_size=50):
        return self.get_call(
            {"datasets__slug": dataset, "page": str(page), "page_size": str(page_size)}
        )
        
    def get_uuid_by_slug(self, slug):
        if "," in slug:
            print("Found", slug.split(","), "as a slug, chose the second")
            slug = slug.split(",")[1]
        return list(self.slug_dict.keys())[list(self.slug_dict.values()).index(slug)]
    
    def get_raster_by_dataset(self, dataset_slug, raster_slug, pages=10):
        for page in range(1, pages + 1):
            results = self.dataset_search(page, dataset_slug)
            result = self.match_results_to_slug(results['results'], raster_slug)
            if result:
                return result
            if not results['next']:
                break
        
        return None

    def get_raster_by_slug(
        self, slug, search="last_modified", organisation=None, max_pages=10
    ):

        for page in range(1, max_pages + 1):
            if search == "last_modified":
                results = self.last_modified_raster_search(page)
                result = self.match_results_to_slug(results['results'], slug)
                if result:
                    return result
                
                if not results['next']:
                    break
                    
            elif search == "organisation":
                results = self.organisation_search(page, organisation, 
                                                   page_size=1000)
                result = self.match_results_to_slug(results, slug)
                if result:
                    return result
            else:
                pass

        return None
    def match_results_to_slug(self, results, slug):
        for raster in results:
            if slug == raster["wms_info"]["layer"]:
                return raster
            else:
                pass

        return None

    def get_organisation_uuid(self, organisation):
        r = self.get_call({"name__icontains": organisation}, self.organisation_url,)
        self.organisation_uuid = r.json()["results"][0]["uuid"]
        return r.json()["results"][0]

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
        

        slug = self.get_slug(config)
        if "uuid" in config:
            self.delete_store(config["uuid"])
            return self.reset_config(config)
        else:
            try:
                uuid = self.get_uuid_by_slug(config['slug']) 
                self.delete_store(uuid)
            except Exception as e:
                pass
                #print('Error is', e, 'Updating local slug dictionary')
                
                # path = os.path.dirname(os.path.realpath(__file__))
                # self.slug_dict = load_slug_dict(self.raster_url, 
                #                                 self.headers, 
                #                                 path,
                #                                 update=True)
                
                # try:
                #     uuid = self.get_uuid_by_slug(config['slug']) 
                #     self.delete_store(uuid)
                # except Exception as e:
                #     print('Error is', e, 'Still a failure, trying different methods')

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
            print("Overwrite True but store does not exist or could not" " be found")
            return None

    def delete_store(self, uuid):
        r = delete(url=self.raster_url + uuid + "/", headers=self.headers)
        if r.status_code == 204:
            print("delete store succes", r.status_code)
        else:
            print("delete store failure:", r.json())
            
    def create_source(self, config):
        """ creates a new source"""
        self.r = self.post_call({'data': json.dumps(config)},
                                url=self.sources_url)
        self.source_uuid = self.r['uuid']
        self.source_block = create_source_block(self.source_uuid)
        #return r

    def create_layer(self, config, overwrite=False):
        """ creates new store layer with new data"""
        
        if overwrite:
            new_config = self.overwrite_store(config)
            if new_config:
                config = new_config
        self.r = self.post_call({'data':json.dumps(config)})
        
    def create(self, config):
        """ creates both a new source and a layer"""
        self.create_source(config)
        config['source'] = self.source_block
        self.create_layer(config)
        

    def update_data(self, path):
        self.r = self.post_call({'files': {"file": open(path, "rb")}},
                  url=self.sources_url + self.source_uuid + "/data/",
                  headers=self.headers)
        
    def update_config(self, config):
        self.r = patch(url=self.raster_url + self.raster_uuid,
                  data=json.dumps(config), 
                  headers=self.json_headers)
        

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
    if r.status_code == 200:
        return r.json()
    else:
        return ValueError(
            "Call failed with query:",
            "query",
            query,
            "json:",
            r.json(),
        )
    
def post_call_or(params, url, headers):
    
    query = dict(params, **{"url": url, "headers": headers})
    
    r = post(**query)
    print(r.status_code)
    if r.status_code == 201 or r.status_code == 200:
        print('Post Succes, see store.r')
        return r.json()
    else:
        print('Post failure')
        return ValueError("Call failed with query:", 
                          "url", query['url'], 
                          "query",query,
                          "json:", r.json())


def load_slug_dict(raster_url, headers, path, update=True):
    mk_dir(os.path.join(path,"data"))
    slug_dict_path = os.path.join(path, "data/slug_dict.json")
    if not os.path.exists(slug_dict_path) or update:
        print("Did not find slug_dict.json, creating new and starting update")
        print('Creating file at:', slug_dict_path, 'Patience please...')

        r = get_call_or({"page_size": 1}, url=raster_url, headers=headers)

        page_size = 100
        pages = math.ceil(r["count"] / page_size)
        args = [(raster_url, headers, p, pages, page_size) for p in range(1, pages)]
        
        slug_dict = {}
        for arg in args:
            result_dict = mp_slug_search(*arg)
            slug_dict.update(result_dict)
            
        # slug_dict = {}
        # with mp.Pool(processes=10) as pool:
        #     for result_dict in pool.starmap(mp_slug_search, args):
        #         slug_dict.update(result_dict)

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


def create_source_block(uuid):
    return {
    "graph": {
        "rastersource": [
            "lizard_nxt.blocks.LizardRasterSource",
            uuid
        ]
    },
    "name": "rastersource"
}

if __name__ == "__main__":
    os.chdir("C:/Users/chris.kerklaan/Documents/temp")
