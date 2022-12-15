"""Wrapper for calls for BioPortal API

This requires an apikey which must be provided by the application before use"""

import requests

class BioPortal:
    def __init__(self, apikey):
        self.apikey = apikey
        self.auth_header = {"Authorization": f"apikey token={apikey}"}

    def get_snomed(self, term, source):
        url = f"http://data.bioontology.org/ontologies/SNOMEDCT/classes/{term}"
        response = requests.get(url, headers = self.auth_header)

        if response.status_code == 200:
            content = response.json()

            return  {
                "system": "http://snomed.info/sct",
                "code": term,
                "display": content['prefLabel']
            }


_biop = None
def BioPortalClient(apikey=None):
    global _biop
    if apikey is not None:
        _biop = BioPortal(apikey)
    return _biop