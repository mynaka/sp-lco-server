# controllers/entry_controller.py

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Dict, Any
from database import get_neo4j_driver
import json
from jose import jwt, JWTError

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models for request body
class Entry(BaseModel):
    term: str
    term_code: str  # format: <source>:<idnumber> (unique)
    elements: Dict[str, Any]
    associated_terms: Dict[str, List[str]]  # {"relationship": [Term Codes]}

# Function to decode JWT token
def decode_token(token: str):
    try:
        payload = jwt.decode(token, "SECRET_KEY", algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Dependency to get current user
def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

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
                term: $term,
                term_code: $term_code,
                elements: $elements
            })
            RETURN id(e) AS entry_id
            """,
            term=entry.term,
            term_code=entry.term_code,
            elements=elements_str
        )

        entry_id = result.single()["entry_id"]

        # Create relationships for associated_terms
        for relationship, term_codes in entry.associated_terms.items():
            for term_code in term_codes:
                session.run(
                    """
                    MATCH (e1:Entry {term_code: $term_code1}), (e2:Entry {term_code: $term_code2})
                    CREATE (e1)-[:ASSOCIATED_WITH {relationship: $relationship}]->(e2),
                           (e2)-[:ASSOCIATED_WITH {relationship: $relationship}]->(e1)
                    """,
                    term_code1=entry.term_code,
                    term_code2=term_code,
                    relationship=relationship
                )

        # Create CONTRIBUTOR relationship
        user_id = current_user["id"]
        session.run(
            """
            MATCH (u:User {id: $user_id}), (e:Entry {term_code: $term_code})
            CREATE (u)-[:CONTRIBUTED_TO]->(e)
            """,
            user_id=user_id,
            term_code=entry.term_code
        )

    return {"message": "Entry created successfully"}
