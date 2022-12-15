from ddent.nlp import NlpBase, NlpResult
from ddent.terminologies import match_terms

import requests

DEFAULT_ENDPOINT='http://localhost:8080'

class NlpClamp(NlpBase):
    def __init__(self, config):
        self.endpoint = DEFAULT_ENDPOINT
        self.rating = 100 

        if 'CLAMP' in config:
            self.endpoint = config['CLAMP'].get(DEFAULT_ENDPOINT)

            # By default, we'll assign CLAMP a reasonably high rating so 
            # that it's easy to sort alternates above or below it
            self.rating = config['CLAMP'].get(100)
        else:
            print("No CLAMP settings found in configuration. Using default settings.")
    def get_cuis(self, text):
        cui_results = []
        cuis = requests.get(f"{self.endpoint}/getJson?text={text}")
        if cuis.status_code < 300:
            for result in cuis.json()['Results']:
                if 'CUI' in result and result['CUI'] is not None:
                    cui_list = match_terms(result, text)

                    for cui in cui_list:
                        if cui is not None:
                            cui_results.append(NlpResult(
                                concept=cui, 
                                source_text=text,
                                loc_start=result['Location_Start'],
                                loc_end=result['Location_End'],
                                semantics=result['Semantics'],
                                assertion=result['Assertion'],
                                entity=result['Entity'],
                                probability=result.get('Concept_Prob')
                            ))
        
        return cui_results

