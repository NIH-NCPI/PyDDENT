__version__="0.0.1"

ddent_properties = {
    "urlbase" : "http://ddent.ncpi.someplace.org/ddent-fhir",
    "equivalence": "equivalent"
}

def build_uri(resource_type, system_type, name):
    return f"{ddent_properties['urlbase']}/{resource_type}/{system_type}/{name}"