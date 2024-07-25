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
from utils.auth import get_current_user
from utils.entry_helper import *

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create entry route
@router.post("/create")
async def create_entry(entry: Entry, current_user: dict = Depends(get_current_user)):
    """Create entry for Neo4J database"""
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

@router.get("/all")
async def get_all_entries():
    """Get all existing entries from all databases.

    Returns names and codes of all entries. Used for Landing Page Search Bar.
    """
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
    """Get all entries from a given database. 
    
    Returns it in a Tree structure processable by PrimeVue.
    """
    try:
        # Neo4j query to fetch entries and their parent relationships
        query = (
            """
            MATCH (e:Entry)
            WHERE e.term_code STARTS WITH $database
            OPTIONAL MATCH (e)-[:subset_of]->(parent:Entry)
            OPTIONAL MATCH (e)-[:equivalent_to]-(equivalent:Entry)
            RETURN e, COLLECT(parent) as parents, COLLECT(equivalent) as equivalents
            """
        )

        # Execute query
        with get_neo4j_driver().session() as session:
            result = session.run(query, database=database)

            entry_dict = {}
            child_parent_relations = []

            for record in result:
                entry = record["e"]
                parents = record["parents"]
                equivalents = record["equivalents"]
                term_code = entry["term_code"]
                
                # Create entry data
                entry_data = {
                    "key": term_code,
                    "label": entry["name"],
                    "data": {
                        "term_code": term_code,
                        "elements": entry["elements"],
                        "parents": [{"name": parent["name"], "code": parent["term_code"]} for parent in parents],
                        "equivalents": [{"name": equivalent["name"], "code": equivalent["term_code"], "database": determine_database(equivalent["term_code"])} for equivalent in equivalents]
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
    """Synthesize JSON from a JSON/OBO ontology entry."""
    content = await file.read()
    if file.content_type == 'application/json':
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=str(json.JSONDecodeError))
        
        if "id" in data:
            if data["id"].startswith("http://purl.obolibrary.org/obo/DOID_"):
                return get_do_data_json(data)
        else:
            return {"status": "422", "error": "Unprocessable entity"}
    elif file.filename.lower().endswith('.obo'):
        try:
            # Assuming OBO file content needs specific processing
            return get_mondo_obo_json(content.decode('utf-8'))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))