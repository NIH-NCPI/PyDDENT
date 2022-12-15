"""This is just a simple function to pull the contents from the DbGAP FTP site (XML File) for a singular table
and extract the contents into a CodeSystem suitable for ddent"""

import pdb

import re
from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree
from ddent import ddent_properties

ddregx = re.compile(r'.data_dict[0-9a-zA-Z_]*.xml')
idregx = re.compile(r'phs[0-9]+.v[0-9]+.p[0-9]+')
tidregx = re.compile(r'.pht0*([0-9]+).')
dstname = re.compile("<b>Dataset Name</b>: ([A-Za-z_0-9]+)<br/>")
dstdesc = re.compile("<dt>Dataset Description</dt>\n<dd>\n<p>([\w\s\.]+)</p>")

def extract_xmls_for_id(id):
    study_id = id.split(".")[0]
    url = f"https://ftp.ncbi.nlm.nih.gov/dbgap/studies/{study_id}/{id}/pheno_variable_summaries/"
    response = requests.get(url)
    xmls = {}
    table_desc = None
    if response.status_code == 200:
        page_content = BeautifulSoup(response.content, "html.parser")
        for anchor in page_content.find_all("a"):
            if ddregx.search(anchor.text) is not None:
                xml = f"{url}/{anchor.text}"   
                tid = tidregx.search(xml)
                table_name = study_id
                if tid:
                    tid = tid.groups()[0]
                    table_name = tid
                    table_page_url = f"https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/dataset.cgi?study_id={id}&pht={tid}"
                    print(table_page_url)
                    #pdb.set_trace()
                    try:
                        t_content = requests.get(table_page_url)
                        if t_content.status_code == 200:

                            soup = BeautifulSoup(t_content.text, "html.parser")
                            for b in soup.find_all('b'):
                                if b.text == 'Dataset Name':
                                    table_name = b.next_sibling.string.replace(": ", "")

                            for dt in soup.find_all('dt'):
                                if dt.text == 'Dataset Description':
                                    table_desc = dt.find_next("p").text
                        print(f"\t{tid} - {table_name} | {table_desc}")
                    except:
                        print(f"There was a problem with getting the table name for table: {tid}")
                        pass
                        
                xmls[xml] = (table_name, table_desc)
    return xmls

def transform_to_codesystem(xml_url, tname=None, tdesc=None, codesystem=None, add_extras=False):
    response = requests.get(xml_url)

    if response.status_code < 300:
        data = xml.etree.ElementTree.fromstring(response.text)
        table_id = data.attrib['id']
        study_id = data.attrib['study_id']
        table_name = tname
        table_desc = tdesc

        if table_desc is None:
            table_desc = tname
        variables = []

        # For DbGAP, the study id actually comprises the table ID, so 
        # there really isn't a need to duplicate it. But, we'll add
        # a check just in case
        table_identifier = f"{table_id}.{study_id}"
        if table_id in study_id:
            table_identifier = study_id

        if table_name == study_id:
            table_name = table_identifier

        for var in data:
            if var.tag == 'description':
                if var.text:
                    table_desc = var.text
                    
            elif var.tag not in ('unique_key', 'has_coll'):
                try:
                    vardesc =  var.find('description').text
                except:
                    vardesc = ""
                try:
                    variables.append({
                        "code": var.get('id'),
                        "display": var.find('name').text,
                        "definition" : vardesc
                    })
                    print(variables[-1])
                except:
                    pdb.set_trace()
                    print(var.text)

                # Do we want to capture min/max/units information as well?
                if add_extras:
                    try: 
                        variables[-1]['type'] = var.find('type').text.lower()
                    except:
                        pass
                
                    # Coding details
                    try:
                        codes = var.findall('value')
                        if len(codes) > 0:
                            #pdb.set_trace()
                            codings = []
                            for code in codes:
                                attribs = code.attrib
                                code_value = attribs['code']
                                value = code.text
                                codings.append({
                                    'code': code_value,
                                    'display': value 
                                })
                            variables[-1]['coded_values'] = codings
                            print(codings)
                    except:
                        pass

                    try:
                        variables[-1]['comment'] = var.find('comment').text
                    except:
                        pass                        

                    #pdb.set_trace()

                    try:
                        variables[-1]["unit"] = var.find('unit').text
                    except:
                        pass

                    try:
                        variables[-1]["logical_min"] = var.find('logical_min').text
                    except:
                        pass
                
                    try:
                        variables[-1]['logical_max'] = var.find('logical_max').text
                    except:
                        pass

        if table_name is None or table_name.strip() == "":
            table_name = f"DD Vars for {table_id}"
        
        if table_desc is None:
            table_desc = table_name
        if codesystem is None:
            return {
                "resourceType": "CodeSystem",
                "url": f"{ddent_properties['urlbase']}/CodeSystems/DD/DbGAP/{study_id}/{table_identifier}",
                "identifier": [{
                    "system": f"{ddent_properties['urlbase']}/study/cs/dd",
                    "value": table_identifier
                }],
                "name": f"{table_identifier}",
                "title": table_name,
                "status": "draft",
                "experimental" : False,
                "description": table_desc,
                "content": "complete",
                "caseSensitive" : True,
                "concept" : variables,
                "count": len(variables)
            }
        else:
            codesystem['concept'] += variables
            codesystem['count'] = len(codesystem['concept'])
            return codesystem

