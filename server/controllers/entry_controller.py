# controllers/entry_controller.py
import re
import json
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends
from fastapi.security import OAuth2PasswordBearer

from database import get_neo4j_driver
import json

#Models
from models.entry_model import Entry

#Utilities
from utils.file_helper import *
from utils.auth import *

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create entry route
@router.post("/create")
async def create_entry(entry: Entry, current_user: dict = Depends(get_current_user)):
    elements_str = json.dumps(entry.elements)  # Convert elements dictionary to string

    with get_neo4j_driver().session() as session:
        # Check if the term_code is unique
        result = session.run(
            "MATCH (e:Entry {term_code: $term_code}) RETURN e",
            term_code=entry.term_code
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Term code already exists")

        # Create the entry node
        result = session.run(
            """
            CREATE (e:Entry {
                name: $name,
                term_code: $term_code,
                elements: $elements
            })
            RETURN elementId(e) AS term_id, e.name AS name, e.term_code AS term_code, e.elements AS elements
            """,
            name=entry.name,
            term_code=entry.term_code,
            elements=elements_str
        )
        created_entry = result.single()
        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")

        # Create relationships for associated_terms
        for relationship, term_codes in entry.associated_terms.items():
            for term_code in term_codes:
                session.run(
                    f"""
                    MATCH (e1:Entry {{term_code: $term_code1}}), (e2:Entry {{term_code: $term_code2}})
                    CREATE (e1)-[:{relationship}]->(e2)
                    """,
                    term_code1=entry.term_code,
                    term_code2=term_code,
                )

    return {"status": 200, "term": {created_entry["name"], created_entry["term_code"], created_entry["elements"]}}

# Read all entries route (For Searchbar)
@router.get("/all")
async def get_all_entries():
    try:
        with get_neo4j_driver().session() as session:
            result = session.run(
                """
                MATCH (e:Entry)
                RETURN e.name AS name, e.term_code AS term_code
                """
            )
            entries = []
            for record in result:
                entries.append({
                    "name": record["name"],
                    "code": record["term_code"]
                })

        return {"status": "200", "entries": entries}

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/database/{database}")
async def get_entries(database: str):
    try:
        # Neo4j query to fetch entries and their parent relationships
        query = (
            """
            MATCH (e:Entry)
            WHERE e.term_code STARTS WITH $database
            OPTIONAL MATCH (e)-[:subset_of]->(parent:Entry)
            RETURN e, COLLECT(parent) as parents
            """
        )

        # Execute query
        with get_neo4j_driver().session() as session:
            result = session.run(query, database=database)
            
            entries = []
            entry_dict = {}
            child_parent_relations = []

            for record in result:
                entry = record["e"]
                parents = record["parents"]
                term_code = entry["term_code"]
                
                # Create entry data
                entry_data = {
                    "key": term_code,
                    "label": entry["name"],
                    "data": {
                        "term_code": term_code,
                        "elements": entry["elements"],
                        "parents": [parent["term_code"] for parent in parents]
                    },
                    "children": []
                }
                
                # Store entry data
                entry_dict[term_code] = entry_data

                # Store child-parent relationships
                for parent in parents:
                    child_parent_relations.append((term_code, parent["term_code"]))

            # Construct the hierarchy
            for child_code, parent_code in child_parent_relations:
                if parent_code in entry_dict:
                    entry_dict[parent_code]["children"].append(entry_dict[child_code])

            # Extract root entries
            root_entries = [entry for entry in entry_dict.values() if not entry["data"]["parents"]]

        return {"status": "200", "entries": root_entries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/file")
async def get_data(file: UploadFile = File(...)):
    if file.content_type == 'application/json':
        content = await file.read()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=str(json.JSONDecodeError))
        
        if "id" in data:
            if data["id"].startswith("http://purl.obolibrary.org/obo/DOID_"):
                file.file.seek(0)
                return await get_dodata_json(file)
        else:
            return {"status": "422", "error": "Unprocessable entity"}
    
@router.post("/translate")
async def translate_to_json(file: UploadFile = File(...)):
    # Read file content as bytes and decode to string
    content = await file.read()
    content_str = content.decode('utf-8')

    # Initialize variables to store parsed data
    entry = {}
    elements = {}

    synonym_matches = re.findall(r'synonym: "(.*?)" (EXACT|RELATED|NARROW|BROAD| ) \[.*?\]', content_str)

    entry["name"] = re.search(r'name: (.*)', content_str).group(1)
    entry["term_code"] = re.search(r'id: (.*)', content_str).group(1)
    def_match = re.search(r'def: "(.*?)" \[([^\[\]]+)\]', content_str)
    elements["definition"] = def_match.group(1).strip()
    elements["definition_xrefs"] = [def_match.group(2).strip()]
    elements["subsets"] = re.findall(r'subset: (.*)', content_str)
    elements["synonyms"] = [f'{match[0]} [{match[1]}]' for match in synonym_matches]
    elements["xrefs"] = re.findall(r'xref: (.*)', content_str)
    elements["alternative_ids"] = re.findall(r'alt_id: (.*)', content_str)

    is_a_matches = re.findall(r'is_a: (\S+)(?: \{.*\})?(?: ! (.*))?', content_str)
    associated_terms = {}
    if is_a_matches:
        associated_terms["subset_of"] = []
        for match in is_a_matches:
            code = match[0].strip()
            term = match[1].strip() if match[1] else code
            associated_terms["subset_of"].append({"term": term, "code": code})

    entry["elements"] = elements
    entry["associated_terms"] = associated_terms
    response = {
        "status": "200",
        "entry": entry
    }

    return response