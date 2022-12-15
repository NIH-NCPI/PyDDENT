from copy import deepcopy
from ddent.nlm import NlmClient 
from ddent.bioportal import BioPortalClient
from pprint import pformat

import pdb

import re

def NameCui(term, source):
    client = NlmClient()
    if client is not None:
        return client.get_cui(term, source)

def NameRxNorm(term, source):
    client = NlmClient()
    if client is not None:
        return client.get_rxnorm(term, source)

def NameSnomed(term, source):
    client = BioPortalClient()

    if client is not None:
        return client.get_snomed(term, source)


_basecs_snomed = {      
    "resourceType": "CodeSystem",
    "id": "snomed-ct",
    "url": "http://snomed.info/sct",
    "name": "snomed-ct",
    "title": "SNOMED CT",
    "status": "draft",
    "experimental": False,
    "description": "SNOMED CT",
    "content": "fragment",
    "caseSensitive": True
}

_basecs_umls = {
    "resourceType" : "CodeSystem",
    "url" : "http://terminology.hl7.org/CodeSystem/umls",
    "identifier" : [
        {
            "system" : "urn:ietf:rfc:3986",
            "value" : "urn:oid:2.16.840.1.113883.6.86"
        }
    ],
    "version" : "2.0.0",
    "name" : "Umls",
    "title" : "Unified Medical Language System",
    "status" : "active",
    "experimental" : False,
    "content": "fragment",
    "description" : "UMLS codes as CUIs making up the values in a coding system. More information may be found at http://www.nlm.nih.gov/research/umls/",
}

_basecs_rxnorm = {
    "resourceType": "CodeSystem",
    "id": "rxnorm",
    "url": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "name": "RxNorm",
    "title": "RxNorm",
    "status": "draft",
    "experimental": False,
    "description": "RxNorm",
    "caseSensitive": True,
    "content": "fragment"
}


class ExternalSystem:
    """Represents a single external terminology such as SNOMED or RxNorm. This can build VS and CodeSystems. """
    def __init__(self, name, regex, use_findall, base_cs, display_source=None):
        self.name = name
        self.matchers = [re.compile(x) for x in regex]
        self.use_findall = use_findall
        self.base_cs = base_cs
        self.url = base_cs['url']
        self.codes = {}
        self.changes_made = 0                       # Tracks number of codes inserted since last save/load
        self.display_source = display_source        # This is the function that will attempt to identify the code
    
    def pull_current_version(self, fhirclient):
        """Load whatever we have previously found for the given CS"""
        response = fhirclient.get(f"CodeSystem?url={self.url}")

        if response.success():
            for entry in response.entries:
                # For some things like SNOMED, some FHIR Servers will have some
                # content, including stuff like filters that we don't want to 
                # overwrit. 
                self.base_cs = entry['resource']
                #pdb.set_trace()
                if 'concept' in entry['resource']:
                    for concept in entry['resource']['concept']:
                        self.codes[concept['code']] = concept
                        self.codes[concept['code']]['system'] = self.url
        return response

    def get_codesystem(self):
        self.base_cs['concept'] = []
        for code in self.codes:
            self.base_cs['concept'].append({
                'code': code,
                'display' : self.codes[code]['display']
            })
        
        self.base_cs['count'] = len(self.codes)

        if self.base_cs['count'] > 0:
            self.base_cs['content'] = "fragment"
        return self.base_cs

    def push_current_version(self, fhirclient):
        """Save the CS back to the fhir server, assuming we added some new codes since it was last saved/loaded"""
        cs = self.get_codesystem()
        response = fhirclient.load("CodeSystem", cs)
        self.changes_made = 0

        return response

    def get_vs_concept(self, cui, source):
        if cui not in self.codes:
            concept = self.display_source(cui, source)
            if concept:
                self.codes[cui] = concept
                self.changes_made += 1

        return self.codes.get(cui)        

    def match(self, cui_data, chars_used, orig_text):
        chars_spanned = 0
        cui_list = set()
        matched_concepts = []
        for rex in self.matchers:
            if chars_spanned > 0:
                chars_spanned += 1
            if self.use_findall:
                matches = rex.findall(cui_data)
                if len(matches) == 0:
                    matches = None
                else:
                    for cui in matches:
                        chars_spanned += len(cui)
                        
                        cui_list.add(cui)

                    chars_spanned += len(matches) - 1
            else:
                matches = rex.search(cui_data)
                if matches:
                    gspan = matches.span()
                    chars_spanned += (gspan[1] - gspan[0])

                    for group in matches.groups():
                        for cui in group.split(","):
                            cui_list.add(cui)

        for cui in cui_list:
            cui = self.get_vs_concept(cui, orig_text)

            if cui is not None:
                matched_concepts.append(cui)

        if len(matched_concepts) > 0 and chars_used > 0:
            chars_used += 1
        chars_used += chars_spanned

        return (matched_concepts, chars_used)

_external_systems = [
    ExternalSystem("SNOMED", [r"SNOMEDCT_US\[([0-9,]+)\]"], False, _basecs_snomed, display_source=NameSnomed),
    ExternalSystem("UMLS", [r"(C[0-9]+)"], True, _basecs_umls, display_source=NameCui),
    ExternalSystem("RxNorm", [r"RxNorm=\[([0-9,]+)\]", r"Generic=\[([0-9,]+)\]"], False, _basecs_rxnorm, display_source=NameRxNorm)
]

def get_codesystems_used(urls):
    global _external_systems

    codesystems = {}
    for system in _external_systems:
        if system.url in urls:
            codesystems[system.url] = system.get_codesystem()
    return codesystems


def match_terms(nlp_result, orig_text):
    # Quick sanity check to make sure there aren't some vocabularies we aren't supporting
    
    cui_data_raw = nlp_result['CUI']
    # We have some junk that does show up for some searches, so let's strip it out
    cui_data = cui_data_raw.replace("null,", "").replace("null", "")
    data_len = len(cui_data)
    chars_consumed = 0
    concepts = []
    
    for system in _external_systems:
        (concepts_found, chars_consumed) = system.match(cui_data, chars_consumed, orig_text)
        concepts+= concepts_found

    if chars_consumed != data_len:
        sum = 0
        for concept in concepts:
            sum += len(concept['code'])
            print(f" - {len(concept['code'])}/{sum}\t {concept['system']}:{concept['code']} - {concept['display']}")
        print(f"Original Source data: {cui_data}")
        print(f"The concepts: {concepts}")
        pdb.set_trace()
        print(f"Some data was left behind? {chars_consumed} != {data_len}")

    return concepts

def make_cui_valueset(cuivars, url, name, title, desc):
    cui_vs = {
        "resourceType": "ValueSet",
        "url": f"{url}",
        "version": "0.1.0",
        "name": f"{name}",
        "title": f"{title} ValueSet",
        "status": "draft",
        "description": f"{desc}",
        "compose": {
            "include": []
        }
    }

    for system in cuivars:
        inclusion = {
            "system" : system,
            "concept" : []
        }

        for cui in cuivars[system]:
            cuivar = cuivars[system][cui]
            inclusion['concept'].append({
                "code": cuivar.cui,
                "display": cuivar.concept['display']
            })
        cui_vs['compose']['include'].append(inclusion)

    return cui_vs

def load_terminologies(fhirclient):
    for system in _external_systems:
        system.pull_current_version(fhirclient)

def push_changes(fhirclient):
    changes_made = 0
    for system in _external_systems:
        if system.changes_made > 0:
            changes_made += system.changes_made
            system.push_current_version(fhirclient)
    return changes_made



