# controllers/entry_controller.py

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Dict, Any
from database import get_neo4j_driver
import json
import copy
from jose import jwt, JWTError

#Models
from models.entry_model import Entry

#External functions
from controllers.auth_controller import get_current_user

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
            RETURN id(e) AS term_id, e.name AS name, e.term_code AS term_code, e.elements AS elements
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
    index = 0
    try:
        # Neo4j query to fetch entries
        query = (
            "MATCH (e:Entry) "
            "OPTIONAL MATCH (e)-[:subset_of]->(parent:Entry) "
            "WHERE e.term_code STARTS WITH $database "
            "RETURN e, COLLECT(parent) as parents"
        )

        # Execute query
        with get_neo4j_driver().session() as session:
            result = session.run(query, database=database)
            entries = []
            entry_dict = dict()
            for record in result:
                entry = record["e"]
                entry_data = {
                    "key": index,
                    "label": entry["name"],
                    "data": {
                        "parents": record["parents"],
                        "term_code": entry["term_code"]
                    },
                    "children": []
                }
                index+=1
                entry_dict[entry["term_code"]] = entry_data

            result = session.run(query, database=database)
            for record in result:
                entry = record["e"]
                term_code = entry["term_code"]
                parents = record["parents"]

                for parent in parents:
                    parent_code = parent["term_code"]
                    if parent_code in entry_dict:
                        entry_dict[parent_code]["children"].append(entry_dict[term_code])

            entries = [entry for entry in entry_dict.values() if not entry["data"]["parents"]]
        return entries

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))