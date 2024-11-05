import re
from fastapi import HTTPException

from models.entry_model import DOTermData
from models.subset import subset_definitions_instance

def get_do_data_json(data: dict):
    """Synthesize a Disease Ontology entry into a uniform JSON format"""
    try:
        data = DOTermData(**data)
        definition_info = {
            "def": data.meta.definition.val if data.meta.definition else None,
            "xrefs": data.meta.definition.xrefs if data.meta.definition and data.meta.definition.xrefs else None
        }

        term_code = data.id.split("/")[-1].replace("_", ":")
        synonyms = []
        if data.meta.synonyms:
            for synonym in data.meta.synonyms:
                synonym_type = None
                if synonym.pred == 'hasExactSynonym':
                    synonym_type = 'EXACT'
                elif synonym.pred == 'hasRelatedSynonym':
                    synonym_type = 'RELATED'
                elif synonym.pred == 'hasNarrowSynonym':
                    synonym_type = 'NARROW'
                elif synonym.pred == 'hasBroadSynonym':
                    synonym_type = 'BROAD'
                
                if synonym_type:
                    synonyms.append(f"{synonym.val} [{synonym_type}]")
        
        parents = [edge.obj.split("/")[-1].replace("_", ":") for edge in data.edges if edge.pred == "is_a"] if data.edges else []
        subsets = []
        if data.meta.subsets:
            for url in data.meta.subsets:
                subset_id = url.split("#")[-1]
                definition = subset_definitions_instance.get_definition(subset_id)
                subsets.append({"subset": subset_id, "definition": definition})

        alt_ids = [prop.val for prop in data.meta.basicPropertyValues if prop.pred == "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId"] if data.meta.basicPropertyValues else []
        namespace = [prop.val for prop in data.meta.basicPropertyValues if prop.pred == "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace"] if data.meta.basicPropertyValues else []

        elements = {
            "ontology_id": data.id,
            "definition": definition_info["def"] if definition_info["def"] else None,
            "definition_xrefs": definition_info["xrefs"] if definition_info["xrefs"] else None,
            "subsets": subsets,
            "synonyms": synonyms,
            "xrefs": [xref.val for xref in data.meta.xrefs] if data.meta.xrefs else None,
            "alternative_ids": alt_ids if alt_ids!=[] else None,
            "namespace": namespace if namespace!=[] else None
        }

        important_info = {
            "name": data.lbl,
            "term_code": term_code,
            "elements": elements,
            "associated_terms": {}
        }

        if parents:
            important_info["associated_terms"] = {"subset_of": parents}

        return {"status": "200", "entry": important_info}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def get_mondo_obo_json(content):
    content_str = content

    entry = {}
    elements = {}

    synonym_matches = re.findall(r'synonym: "(.*?)" (EXACT|RELATED|NARROW|BROAD| ) \[.*?\]', content_str)

    entry["name"] = re.search(r'name: (.*)', content_str).group(1)
    entry["term_code"] = re.search(r'id: (.*)', content_str).group(1)
    def_match = re.search(r'def: "(.*?)" \[([^\[\]]+)\]', content_str)
    if def_match:
        elements["definition"] = def_match.group(1).strip()
        elements["definition_xrefs"] = [def_match.group(2).strip()]

    subsets = re.findall(r'subset: ([^ ]+)', content_str)
    if subsets:
        elements["subsets"] = [{"subset": subset, "definition": subset_definitions_instance.get_definition(subset)} for subset in subsets]

    synonyms = [f'{match[0]} [{match[1]}]' for match in synonym_matches]
    if synonyms:
        elements["synonyms"] = synonyms

    xrefs = re.findall(r'xref: (.*)', content_str)
    if xrefs:
        elements["xrefs"] = [re.sub(r'\s*\{.*?\}', '', xref).strip() for xref in xrefs]

    alternative_ids = re.findall(r'alt_id: (.*)', content_str)
    if alternative_ids:
        elements["alternative_ids"] = alternative_ids

    is_a_matches = re.findall(r'is_a: (\S+)(?: \{.*\})?(?: ! (.*))?', content_str)
    if is_a_matches:
        associated_terms = {"subset_of": [match[0].strip() for match in is_a_matches]}

    is_a_matches = re.findall(r'is_a: (\S+)(?: \{.*\})?(?: ! (.*))?', content_str)
    associated_terms = {}
    if is_a_matches:
        associated_terms["subset_of"] = []
        for match in is_a_matches:
            code = match[0].strip()
            associated_terms["subset_of"].append(code)

    intersection_of_matches = re.findall(r'intersection_of: (\S+) ! (.*)', content_str)
    if intersection_of_matches:
        elements["intersection_of"] = [{"code": match[0], "term": match[1]} for match in intersection_of_matches]

    relationship_matches = re.findall(r'relationship: (\S+) (\S+) ! (.*)', content_str)
    if relationship_matches:
        associated_terms["relationship"] = [{"relation": match[0], "code": match[1], "term": match[2]} for match in relationship_matches]

    exact_matches = re.findall(r'property_value: skos:exactMatch (\S+)', content_str)
    conforms_to = re.findall(r'property_value: terms:conformsTo (\S+)', content_str)
    if exact_matches:
        associated_terms["equivalent_to"] = []
        for match in exact_matches:
            if not match.startswith("http"):
                associated_terms["equivalent_to"].append(match)
            elements.setdefault("exact_match", []).append(match)
    
    if conforms_to:
        elements["conforms_to"] = conforms_to

    entry["elements"] = elements
    entry["associated_terms"] = associated_terms
    response = {
        "status": "200",
        "entry": entry
    }

    return response

from  utils.entry_helper import query_icd10cm_neo4j
def process_row(row):
    """
    Process a single row by querying notation for each cell.
    """
    for i in range(len(row)):
        label = row[i] 
        notation = query_icd10cm_neo4j(label)
        
        if notation:
            row[i] = notation
    return row