# controllers/entry_controller.py
import csv
from io import StringIO
import os
import re
import json
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Depends
from fastapi.security import OAuth2PasswordBearer
import shutil

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
                MATCH (e:Entity)
                RETURN e.prefLabel AS name, e.notation AS term_code
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
async def get_root_entries(database: str):
    """Get all entries from a given database. 
    
    Returns it in a Tree structure processable by PrimeVue.
    """
    try:
        # Neo4j query to fetch entries and their parent relationships
        query = (
            """
            MATCH (e:Entity)
            WHERE (e.notation STARTS WITH $database + ":" OR e.identifier STARTS WITH $database + ":") AND NOT((e)-[]->())
            RETURN e.prefLabel AS prefLabel, 
                e.notation AS notation, 
                EXISTS(()-[]->(e)) AS hasIncomingRelationships,
                e AS data
            """
        )

        # Execute query
        with get_neo4j_driver().session() as session:
            result = session.run(query, database=database)
            entry_dict = {}

            for record in result:
                entry = record["data"]
                pref_label = record["prefLabel"]
                notation = record["notation"]
                has_incoming_relationships = record["hasIncomingRelationships"]
                
                # Create entry data
                entry_data = {
                    "key": notation,
                    "label": pref_label,
                    "data": entry,
                    "leaf": not has_incoming_relationships,
                    "loading": True
                }
                
                # Store entry data
                entry_dict[notation] = entry_data

            root_entries = list(entry_dict.values())

        return {"status": "200", "entries": root_entries}

    except Exception as e:
        # Handle exceptions, log error, and return an error response
        return {"status": "500", "error": str(e)}


@router.get("/database/{database}")
async def get_root_entries(database: str):
    """Get all entries from a given database. 
    
    Returns it in a Tree structure processable by PrimeVue.
    """
    try:
        # Neo4j query to fetch entries and their parent relationships
        db = database + ":"
        query = (
            """
            MATCH (root:Entity)
            WHERE (root.notation STARTS WITH $db OR root.identifier STARTS WITH $db) AND NOT((root)-[SUBSET_OF]->())
            RETURN root.prefLabel AS prefLabel, 
                root.notation AS notation, 
                EXISTS(()-[]->(root)) AS hasIncomingRelationships,
                root AS data
            """
        )

        # Execute query
        with get_neo4j_driver().session() as session:
            result = session.run(query, database=db)

            entry_dict = {}

            for record in result:
                entry = record["data"]
                pref_label = record["prefLabel"]
                notation = record["notation"]
                has_incoming_relationships = record["hasIncomingRelationships"]
                
                # Create entry data
                entry_data = {
                    "key": notation,
                    "label": pref_label,
                    "data": entry,
                    "leaf": not has_incoming_relationships,
                    "loading": True
                }
                
                # Store entry data
                entry_dict[notation] = entry_data

            root_entries = list(entry_dict.values())

        return {"status": "200", "entries": root_entries}

    except Exception as e:
        return {"status": "500", "error": str(e)}

@router.get("/database/{node_notation}/children")
async def get_children(node_notation: str):
    """Get all children of the given node where a SUBCLASS_OF relationship exists."""
    query = """
    MATCH (child)-[:SUBCLASS_OF]->(parent {notation: $node_notation})
    RETURN child.prefLabel AS prefLabel,
        child.notation AS notation,
        EXISTS(()-[]->(child)) AS hasIncomingRelationships,
        child AS data
    """
    with get_neo4j_driver().session() as session:
        result = session.run(query, node_notation=node_notation)

        children_dict = {}

        for record in result:
            entry = record["data"]
            pref_label = record["prefLabel"]
            notation = record["notation"]
            has_incoming_relationships = record["hasIncomingRelationships"]
            
            # Create entry data
            entry_data = {
                "key": notation,
                "label": pref_label,
                "data": entry,
                "leaf": not has_incoming_relationships,
                "loading": True
            }
            
            # Store entry data
            children_dict[notation] = entry_data

        children_entries = list(children_dict.values())

    return {"status": "200", "entries": children_entries}
neo4j_loader = Neo4jLoader()

@router.on_event("shutdown")
async def shutdown_event():
    neo4j_loader.close()  # Close Neo4j connection when the app shuts down

# Endpoint to load TTL ontology into Neo4j
@router.post("/load_ontology")
async def load_ontology(file_path: str = Form(...)):
    try:
        rdf_graph = parse_ttl(file_path)
        triples = extract_all_data_icd10cm(rdf_graph)
        neo4j_loader.create_nodes(triples)
        return {"message": "Ontology loaded successfully"}
    except:
        return {"message": file_path}

# Endpoint to query a term from Neo4j
@router.post("/get_code")
async def get_term_code(label: str = Form(...)):
    notation = neo4j_loader.query_icd10cm_neo4j(label)
    return notation

@router.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV file, process it, and return the updated content.
    """
    try:
        content = await file.read()
        
        csv_data = StringIO(content.decode("utf-8"))
        csv_reader = csv.reader(csv_data)
        
        updated_rows = []
        
        header = next(csv_reader)
        
        for row in csv_reader:
            for i in range(len(row)):
                label = row[i]  # Get the current cell value
                notation = neo4j_loader.query_icd10cm_neo4j(label)
            
                if notation:
                    row[i] = notation  # Update the cell with the notation/identifier

            updated_rows.append(row)
        
        return {
            "status": "200",
            "header": header,
            "updated_data": updated_rows
        }
    except:
        return {"message": content}