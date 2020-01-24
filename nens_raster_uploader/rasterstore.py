# Documentation https://demo.lizard.net/doc/api.html#post--api-v3-rasters-


# System imports
import sys
#sys.path.append("C:/Users/chris.kerklaan/Documents/base_modules")

# Third-party imports
import json
from requests import get, post, codes, delete
from tqdm import tqdm

# Local imports
from nens_gs_uploader.localsecret.localsecret import username, password

class rasterstore(object):
    def __init__(self, username=username, password=password):
        self.username = username
        self.password = password
        self.raster_url = "https://demo.lizard.net/api/v4/rasters/"
        self.search_url = "https://demo.lizard.net/api/v4/search/"
        #self.raster_uuid = "https://demo.lizard.net/api/v4/rasters/{uuid}/"
        self.organisation_url = "https://demo.lizard.net/api/v4/organisations/"

        self.post_headers = {
            "username": username,
            "password": password,
            "Content-Type": "application/json",
        }
        self.get_headers = {"username": username,
                            "password": password}

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
            url=self.raster_url + "?ordering=-last_modified&page={}&page_size={}".format(str(page), str(page_size)),
            headers=self.get_headers,
        )
        if r.status_code == 200:
            return r.json()['results']
        else:
            return ValueError("Get Last modified failure")
        
    def organisation_search(self, page, organisation, page_size=50):
        r = get(
            url=self.raster_url + "?organisation__uuid={}&page={}&page_size={}".format(str(organisation), str(page), str(page_size)),
            headers=self.get_headers,
        )
        if r.status_code == 200:
            return r.json()['results']
        else:
            return None
    
    def match_results_to_slug(self, results, slug):
        for raster in results:
            if slug == raster['wms_info']['layer']:
                return raster
            else:
                pass
            
        return None
    
    def get_raster_by_slug(self, slug, search='last_modified', organisation = None, pages=10):
        
        print('Searching {} pages'.format(pages))
        for page in tqdm(range(1, pages + 1)):
            if search == 'last_modified':
                results = self.last_modified_raster_search(page)
                result = self.match_results_to_slug(results, slug)
                if result is not None:
                    return result
                
            elif search == 'organisation':
                results = self.organisation_search(page, organisation, page_size=1000)
                result = self.match_results_to_slug(results, slug)
                if result is not None:
                    return result
            else:
                pass
            
        return None
    
    def get_store(self, search_terms, slug, method="search", uuid=None):
        if method == "search":
            search_terms_new = [] 
            for term in search_terms:
                search_terms_new.append(term)
                search_terms_new.append(term.upper())
                search_terms_new.append(term.lower())
            
            search_terms = list(set(search_terms_new + [slug] + slug.split(":")))
            #print("search terms..", search_terms)
            
            for search_term in list(set(search_terms)):
                #print("search name...",search_term )
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
                #print("search organisation...",search_term )
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
            r = get(
                    url=self.raster_url + uuid +"/",
                    headers=self.get_headers
                    )
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
        
        r = delete(
            url=self.raster_url+ uuid + "/",
            headers=self.get_headers
        )
        if r.status_code == 204:
            print('delete store succes', r.status_code)
        else:
            print("delete store failure:", r.json())

    def create(self, configuration, overwrite=False):
        if overwrite:
            raster = self.get_raster_by_slug(configuration['slug'])
            if raster is not None:
                self.delete_store(raster['uuid'])
            else:
                print('Overwrite true but store does not exist')
                
        configuration["organisation"] = self.organisation_uuid
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
    

    def post_data(self, path):
        print(path)
        url = self.raster_url + self.raster_uuid + "/data/"
        
        r = post(
            url=url,
            files={"file": open(path, "rb")},
            headers=self.get_headers,
        )

        if not r.status_code == codes.ok:
            print("post data failure", r.status_code)
            print(r.json())

        else:
            print("post data succes", r.status_code)


if __name__ == "__main__":
    pass
