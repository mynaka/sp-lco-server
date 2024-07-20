from fastapi import File, HTTPException, UploadFile
#Models
from models.entry_model import DOTermData
from models.subset import subset_definitions_instance

async def get_dodata_json(file):
    try:
        content = await file.read()
        data = DOTermData.parse_raw(content)

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
            "definition": definition_info if definition_info["def"] or definition_info["xrefs"] else None,
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