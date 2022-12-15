"""Interface for NLM api """

import re
from datetime import datetime, timedelta
import requests
from pprint import pformat
import csv

import pdb

_nlm_api_key_url = "https://utslogin.nlm.nih.gov/cas/v1/api-key"
_nlm_service_ticket_url = "https://utslogin.nlm.nih.gov/cas/v1/tickets/"
_nlm_fhir_srvr_url = "https://cts.nlm.nih.gov/fhir/r4/"

# For now, just use this as a var. Once we get the details worked out, 
# we can move it into a private area

tgt_extractor = re.compile(r'action="https://utslogin.nlm.nih.gov/cas/v1/api-key/(TGT-[0-9a-zA-Z-]+)')

_nlm_error_file = None
_nlm_error_log = None

def nlm_error_write(desc, system_source, code):
    global _nlm_error_log, _nlm_error_file

    if _nlm_error_log:
        _nlm_error_log.writerow([desc, system_source, code])
        _nlm_error_file.flush()

def nlm_error_log(fn=None):
    global _nlm_error_file, _nlm_error_log

    if fn is not None:
        _nlm_error_file = open(fn, 'wt')
        _nlm_error_log = csv.writer(_nlm_error_file, delimiter='\t', quotechar='"')
        nlm_error_write('Var_Description', 'System_Source', 'Code')
    
    return _nlm_error_log

class NlmApi:
    # We are defaulting to the 8 hours which applies to the TGT
    class Ticket:
        def __init__(self, ticket_data, ticket_eol=28800):
            self.ticket = ticket_data
            self.expires = datetime.now() + timedelta(seconds=ticket_eol - 1)

        def valid(self):
            return datetime.now() < self.expires
    def __init__(self, apikey):
        self.key = apikey
        self.tgt = None

    def get_tgt(self):
        if self.tgt is None or not self.tgt.valid():
            response = requests.post(_nlm_api_key_url, 
                                        data={"apikey":self.key}, 
                                        headers={'content-type': 'application/x-www-form-urlencoded'})

            if response.status_code == 201:
                body = response.text
                match = tgt_extractor.search(body)
                if match:
                    self.tgt = NlmApi.Ticket(match.groups()[0])

        return self.tgt 

    def _get(self, endpt):
        tgt = self.get_tgt()

        ticket_url = f"{_nlm_service_ticket_url}{tgt.ticket}"
        response = requests.post(ticket_url, 
                                    data={'service': 'http://umlsks.nlm.nih.gov'}, 
                                    headers={'content-type': 'application/x-www-form-urlencoded'})
        if response.status_code == 200:
            # And the response text should be the key
            ticket = response.text 
            return requests.get(f"{endpt}?ticket={ticket}")
        print(response.text)
        return response

    def get_snomed(self, id):
        url = f"{_nlm_fhir_srvr_url}"

    def get_aui(self, cui):
        url = f"https://uts-ws.nlm.nih.gov/rest/content/current/AUI/{cui}"
        response = self._get(url)

        content = response.json()
        cui_name = content['result']['name']

        return {
            "system": "http://terminology.hl7.org/CodeSystem/umls",
            "code": cui,
            "display": cui_name
        }

    def get_rxnorm(self, id, source):
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{id}.json"
        print(f"The URL: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            content = response.json()

            if 'name' not in content['idGroup']:
                print(pformat(content))
                #pdb.set_trace()
                nlm_error_write(source, 'RxNorm', id)
                return {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code" : id, 
                    "display": f"No Name Found For '{source}"
            }
            return {
                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                "code" : id, 
                "display": content['idGroup']['name']
            }

    def get_cui(self, cui, source):
        #pdb.set_trace()
        url = f"https://uts-ws.nlm.nih.gov/rest/content/current/CUI/{cui}"
        response = self._get(url)

        try:
            content = response.json()
            if 'name' not in content['result']:
                print(pformat(content))
                pdb.set_trace()
            cui_name = content['result']['name']
            #print(f"The name for {cui}: {cui_name}")

            return {
                "system": "http://terminology.hl7.org/CodeSystem/umls",
                "code": cui,
                "display": cui_name
            }
        except:
            if response is not None:
                print(pformat(response.text))
            print(f"There was a problem with getting data for {url}")
            nlm_error_write(source, 'UMLS', cui)
            return {
                "system": "http://terminology.hl7.org/CodeSystem/umls",
                "code": cui,
                "display": f"No Matching Concept Found For '{source}'"
            }
_nlm = None
def NlmClient(apikey=None):
    global _nlm
    if apikey is not None:
        _nlm = NlmApi(apikey)
    return _nlm