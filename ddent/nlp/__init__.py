"""
Provide a common interface for different NLP systems. 
"""

from pathlib import Path
from importlib import import_module
from collections import defaultdict
import sys
import requests

import pdb

def camelize(val):
    """Convert a snake-case filename to it's CameCase object name"""
    return val.title().replace("_", "")

# Cache the NLP modules in case we need to generate more than one
_modules = None

# sorted list of modules which were found to be "live" 
_active_modules = []

_default_module = None

def default_nlp_module(pref=None):
    global _default_module

    if pref:
        _default_module = pref
    
    return _default_module

def get_extraction_modules(config):
    """Return the available auth modules, scanning the fhir_auth directory if necessary to find all modules."""
    global _modules, _active_modules

    # We'll cache the scan to avoid having to redo this work over again
    if _modules is None:
        _modules = {}
        # Discover all of the authentication modules
        mod_dir = Path(__file__).parent

        module_ratings = defaultdict(list)

        module_files = mod_dir.glob("nlp_*.py")
        for module in module_files:
            # IDs are just the name of the module's filename without path or extension
            module_id = module.stem
            module_name = f"ddent.nlp.{module_id}"
            mod = import_module(module_name)

            # The class is presumed to be the camelcase version of the filename 
            # TODO Decide if its better to drop the Auth from those camel case classnames?
            module_class_name = camelize(module_id)
            auth_class = getattr(mod, module_class_name)

            # Add the class to the cache so that we can instantiate it if need be
            nlp_module = auth_class(config)
            _modules[module_id] = nlp_module

            if nlp_module.is_live():
                module_ratings[nlp_module.rating].append(nlp_module)
        
        for rating in sorted(module_ratings.keys())[::-1]:
            _active_modules += module_ratings[rating]

        # Go ahead and set the default to be the first active module with 
        # the highest rating
        default_nlp_module(_active_modules[0])

    return _modules

def get_nlp(nlp_id = None):
    """return an apprpriate authorization object based on the details inside cfg"""   
    global _modules

    if len(_active_modules) < 1:
        print(f"Houston, we have a problem. There are no valid NLP servers available")
        sys.exit(1)

    if nlp_id is None:
        return _active_modules[0]

    return get_extraction_modules().get(nlp_id)

class NlpResult:
    def __init__(self, concept, loc_start, loc_end, source_text, semantics=None, assertion=None, entity=None, probability=None):#          concept, entry, source_text):
        self.start_loc = loc_start
        self.end_loc = loc_end
        self.matched_text = source_text[int(self.start_loc):int(self.end_loc)]
        self.source_text = source_text
        self.semantics = semantics
        self.cui = concept['code']
        self.concept = concept
        self.assertion = assertion
        self.entity = entity
        self.concept_prob = probability

    def system(self):
        return self.concept['system']

    def definition(self):
        entries = ["<ul>"]

        if self.semantics:
            entries.append(f"<li><strong>Semantics:</strong> {self.semantics}</li>")
        if self.assertion:
            entries.append(f"<li><strong>Assertion:</strong> {self.assertion}</li>")
        if self.concept_prob:
            entries.append(f"<li><strong>Prob:</strong> {self.concept_prob}</li>")
        entries.append(f"<li><strong>Loc:</strong> {self.start_loc}-{self.end_loc}</li>")
        entries.append(f"<li><strong>Matched:</strong>{self.matched_text}</li>")
        entries.append(f"<li><strong>Source Text:</strong>{self.source_text}</li>")
        
        entries.append("</ul>")

        return "\t\n".join(entries)
class NlpBase:
    def __init__(self, config):
        self.endpoint = None
        self.rating = -100

    def get_rating(self):
        return self.rating

    def get_cuis(self, text):
        pass

    def is_live(self):
        if self.endpoint:
            try:
                response = requests.get(self.endpoint, timeout=6.0)
                # It doesn't really matter what the response is as long as it doesn't
                # fail to connect
                return True
            except:
                print(f"No meaningful response from: {self.endpoint}")
                pass
        print(f"No endpoint configured for the module {type(self).__name__}")
        return False

