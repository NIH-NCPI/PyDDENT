""" DDENT Python Library

For properly formatted FHIR CodeSystems, this library can extract CUI vars from the variable descript and build out a bidirectional FHIR ConceptMap to enable users to more easily discover datasets suited for their research needs. 

In addition to the base functionality of extracting those CUIS, there are some helper functions to enable extraction from certain sources such as DbGAP data dictionaries. 

A properly formatted CodeSystem includes the following properties for each of the codes:
    code    - This should be the dataset's varname
    display - This could be a short, yet familiar name for the variable 
    definition - This is the complete description of the variable which is to be submitted to NLP for CUI extraction

"""
import requests
import sys
from ddent.terminologies import match_terms, push_changes, make_cui_valueset, get_codesystems_used
from pprint import pformat
from collections import defaultdict
import re

import pdb

from . import ddent_properties, build_uri

def get_cuis(cui_data):
    cuis = []
    varlen = len(cui_data)
    chars_consumed = 0

    return match_terms(cui_data)

#TODO - Change this to accept url, name, title and desc along with an array of code systems. 
# The include will embedd each of the urls
# For the conceptmap, we will need to keep a running dictionary for each direction and append to 
# the lists in case any of our vars are duplicated

def build_valueset(url, name, title, desc, codesystems):
    url = url.replace("CodeSystems", "ValueSets")
    vs = {
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

    for codesystem in codesystems:
        vs['compose']['include'].append({
            'system' : f"{codesystem['url']}"
        })

    if len(vs['compose']['include']) == 0:
        return None
    print(vs['url'])
    return vs

def load_resource(fhirclient, resource_type, resource):
    result = fhirclient.load(resource_type, resource)
    print(f"{resource_type} {resource['url']}")
    if result['status_code'] != 201:
        print(pformat(resource))
        print(pformat(result))
        pdb.set_trace()
        sys.exit(1)    

    return result

# perform the transformation 
def transform_dd_codesystem(study_id, title, desc, codesystems, nlp_endpoint, fhirclient):
    class transform_output:
        def __init__(self, study_id, title, desc):
            self.study_id = study_id
            self.title = title
            self.desc = desc
            self.codesystems = {
                "DD": {},
                "CUI": {}
            }   
            self.valueset = {}         # dd|cui => ingested VS 
            self.conceptmap = {}       # dd|cui => ingested CM 

    cm_dd2cui = None
    cm_cui2dd = None
    vs_dd = None
    vs_cui = None

    cui_cs_used = set()
    transoutput = transform_output(study_id, title, desc)

    class DdVar:
        def __init__(self, entry):
            self.code = entry['code']
            self.display = entry['display']
            self.definition = entry['definition']
            self.cuis = set()

    class CuiVar:
        def __init__(self, concept): #entry, source_text):
            self.nlp_result = concept
            self.cui = concept.cui
            self.concept = concept.concept
            self.vars = set()

        def definition(self):
            return self.nlp_result.definition()

    valid_codesystems = {
        "cui" : [],
        "dd": []
    }
    cui_codesystems = {}        # CUI CS URI => (cui_cs and dd_cs)
    ddvars = {}     # code => DdVar
    cuivars = defaultdict(dict)    # cui.system => CuiVar

    # TODO: We need to block all CM relationships into DD-Table-URL:CUI-URL => [(source, [target])]
    # Numbers shouldn't be too high, so it's probably not horrible to join the systems with a simple
    # defaultdict(list) of tuples. 
    # We have uneven CodeSystems: 3 total CUI CS and N Table Code Systems. So, we need 
    # to be able to organize them appropriately within the element/target

    # ddsystem:cuisystem => { pvh => [cui1, cui2...]}
    table_mappings = defaultdict(lambda: defaultdict(set))
    cui_mappings = defaultdict(lambda: defaultdict(set))

    for codesystem in codesystems:
        table_id = codesystem['name']
        table_uri = codesystem['url']
        
        cuis_added = 0
        for entry in codesystem['concept']:
            ddvar = DdVar(entry)
            ddvars[ddvar.code] = ddvar 

            if ddvar.definition.strip() != "":
                cuis = nlp_endpoint.get_cuis(ddvar.definition)
                # cuis = requests.get(f"{nlp_endpoint}/getJson?text={ddvar.definition}")

                for cui in cuis:
                    code = cui.cui
                    system = cui.system()

                    if code not in cuivars[system]:
                        # We'll be reporting the CUI Code systems that were used
                        # upon return, so let's keep tack of them
                        cui_cs_used.add(system)
                        cuivar = CuiVar(cui) #, ddvar.definition)
                        cuivars[system][code] = (cuivar)

                    mapkey = f"{table_uri}:::{system}"

                    table_mappings[mapkey][ddvar.code].add(code)
                    cui_mappings[mapkey][code].add(ddvar.code)

                    cuivar.vars.add(ddvar)
                    ddvar.cuis.add(code)
                    cuis_added += 1

        if cuis_added > 0:
            push_changes(fhirclient)
            ddresponse = load_resource(fhirclient, "CodeSystem", codesystem)['response']
            valid_codesystems['dd'].append(codesystem)
            #pdb.set_trace()

            transoutput.codesystems['DD'][codesystem['url']] = ddresponse
    transoutput.codesystems['CUI'] = get_codesystems_used(cui_cs_used)
    #pdb.set_trace()
    valueset = build_valueset(build_uri("ValueSet", "DD", f"{study_id}"), study_id, title, desc, valid_codesystems['dd'])
    if valueset == None:
        print(codesystems)
        return transoutput

    valueset['identifier'] = [{
        "system": f"{ddent_properties['urlbase']}/study/vs/dd",
        "value": study_id
    }]
    ddresponse = load_resource(fhirclient, "ValueSet", valueset)['response']

    valueset_cui = make_cui_valueset(cuivars, build_uri("ValueSet", "CUI", f"{study_id}"), study_id + "-CUI", "CUIs for " + title, desc)
    valueset_cui['identifier'] = [{
        "system": f"{ddent_properties['urlbase']}/study/vs/cui",
        "value": study_id
    }]
    cuiresponse = load_resource(fhirclient, "ValueSet", valueset_cui)['response']

    transoutput.valueset['dd'] = ddresponse
    print(ddresponse['url'])
    transoutput.valueset['cui'] = cuiresponse

    cm_name = f"{study_id}-DDtoCUI"
    cm_dd2cui = {
        "resourceType" : "ConceptMap",
        "url": f"{build_uri('ConceptMap', 'DD', cm_name)}",
        "name": cm_name,
        "identifier": {
            "system": f"{ddent_properties['urlbase']}/study/cm/dd-cui",
            "value": study_id
        },
        "title": f"Study Concept Map for {title}",
        "status": "draft",
        "experimental" : False,
        "description": desc,
        "sourceUri": f"{valueset['url']}",
        "targetUri":  f"{valueset_cui['url']}",
        "group" : []
    }   

    cm_name = f"{study_id}-CUItoDD"
    cm_cui2dd = {
        "resourceType" : "ConceptMap",
        "url": f"{build_uri('ConceptMap', 'CUI', cm_name)}",
        "name": cm_name,
        "identifier": {
            "system": f"{ddent_properties['urlbase']}/study/cm/cui-dd/",
            "value": study_id
        },
        "title": f"CUI Concept Map for {title}",
        "status": "draft",
        "experimental" : False,
        "description": desc,
        "sourceUri": f"{valueset_cui['url']}",
        "targetUri":  f"{valueset['url']}",
        "group" : []
    }   

    for csmap in table_mappings:
        urls = csmap.split(":::")
        if len(urls) != 2:
            pdb.set_trace()
        table_url, cui_url = urls[0:2]

        ddgroup = {
            "source": table_url,
            "target": cui_url,
            "element": []
        }

        for code in table_mappings[csmap]:
            # Populate the elements
            element = {
                "code": code,
                "display": ddvars[code].display,
                "target": []
            }

            for cui in table_mappings[csmap][code]:
                concept = cuivars[cui_url][cui].concept
                element['target'].append({
                    "code": cui,
                    "display": concept['display'],
                    "comment": cuivars[cui_url][cui].definition(),
                    "equivalence": ddent_properties['equivalence']
                })
            ddgroup['element'].append(element)
        cm_dd2cui['group'].append(ddgroup)

    for csmap in cui_mappings:
        table_url, cui_url = csmap.split(":::")

        ddgroup = {
            "source": cui_url,
            "target": table_url,
            "element": []
        }
        for code in cui_mappings[csmap]:
            # Populate the elements
            element = {
                "code": code,
                "display": cuivars[cui_url][code].concept['display'],
                "target": []
            }

            for var in cui_mappings[csmap][code]:
                element['target'].append({
                    "code": var,
                    "display": ddvars[var].display,
                    "equivalence": ddent_properties['equivalence']
                })
            ddgroup['element'].append(element)
        cm_cui2dd['group'].append(ddgroup)

    cmddresponse = load_resource(fhirclient, "ConceptMap", cm_dd2cui)['response']

    cmcuiresponse = load_resource(fhirclient, "ConceptMap", cm_cui2dd)['response']

    transoutput.conceptmap['dd'] = cmddresponse
    transoutput.conceptmap['cui'] = cmcuiresponse


    return transoutput

