# controllers/entry_controller.py
import csv
from io import StringIO
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from concurrent.futures import ProcessPoolExecutor

from pydantic import BaseModel

from database import get_neo4j_driver

#Models
from models.entry_model import Entry

#Utilities
from utils.file_helper import *
from utils.auth import get_current_user
from utils.entry_helper import *

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class DataInput(BaseModel):
    prefLabel: str
    identifier: str
    description: str
    format: str
    sample: str
    output: str

# Create entry route
@router.post("/create")
async def create_entry(data: DataInput, current_user: dict = Depends(get_current_user)):
    """Create entry for Neo4J database"""

    with get_neo4j_driver().session() as session:
        # Check if the identifier is unique
        result = session.run(
            "MATCH (e:Table {identifier: $identifier}) RETURN e",
            identifier=data.identifier  # Fixed variable name
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier already exists")

        # Create the entry node
        result = session.run(
            """
            CREATE (e:Table {prefLabel: $prefLabel, identifier: $identifier, description: $description, format: $format, sample: $sample, output: $output})
            RETURN e
            """,
            prefLabel=data.prefLabel,
            identifier=data.identifier,
            description=data.description,
            format=data.format,
            sample=data.sample,
            output=data.output
        )
        created_entry = result.single()
        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")

    return {
        "status": 200,
        "term": {
            "name": created_entry["e"]["prefLabel"],
            "identifier": created_entry["e"]["identifier"],
            "description": created_entry["e"]["description"],
        }
    }
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

@router.get("/search/{searchQuery}")
async def search_entries(searchQuery: str):
    """
    Search for the 10 closest terms to the provided query in Entity nodes based on prefLabel and altLabel.

    Returns:
        A list of up to 10 matched entries.
    """
    try:
        with get_neo4j_driver().session() as session:
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('entityLabelIndex', $query)
                YIELD node, score
                WHERE node.notation IS NOT NULL OR node.identifier IS NOT NULL
                RETURN node.prefLabel AS name, COALESCE(node.notation, node.identifier) AS term_code, score
                ORDER BY score DESC
                LIMIT 5
                """,
                {"query": searchQuery}
            )

            entries = []
            for record in result:
                entries.append({
                    "name": record["name"],
                    "code": record["term_code"],
                    "score": record["score"]
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
            MATCH (e)
            WHERE (e:Entity OR e:Table) AND 
                (e.notation STARTS WITH $database + ":" OR e.identifier STARTS WITH $database + ":") AND 
                NOT((e)-[]->())
            RETURN e.prefLabel AS prefLabel, 
                COALESCE(e.notation, e.identifier) AS notation,
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

@router.get("/database/{node_notation}/children")
async def get_children(node_notation: str):
    """Get all children of the given node where a SUBCLASS_OF relationship exists."""
    query = """
    MATCH (child)-[:SUBCLASS_OF]->(parent)
    WHERE (child:Entity OR child:Table) AND (parent.identifier = $node_notation OR parent.notation = $node_notation)
    RETURN child.prefLabel AS prefLabel,
        COALESCE(child.notation, child.identifier) AS notation,  // Use COALESCE to choose identifier if notation is null
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

@router.on_event("shutdown")
async def shutdown_event():
    get_neo4j_driver().close()

@router.post("/load_ontology")
async def load_ontology(file_path: str = Form(...)):
    try:
        rdf_graph = parse_ttl(file_path)
        triples = extract_all_data_icd10cm(rdf_graph)
        create_nodes(triples)
        return {"message": "Ontology loaded successfully"}
    except:
        return {"message": file_path}

@router.post("/uploadfile/")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV file, process it in parallel, and return the updated content as a CSV file.
    """
    try:
        content = await file.read()
        csv_data = StringIO(content.decode("utf-8"))
        csv_reader = csv.reader(csv_data)
        
        updated_csv = StringIO()
        csv_writer = csv.writer(updated_csv)
        
        header = next(csv_reader)
        csv_writer.writerow(header)

        # Parallel Processing
        with ProcessPoolExecutor() as executor:
            updated_rows = list(executor.map(process_row, csv_reader))
        
        for row in updated_rows:
            csv_writer.writerow(row)
        
        updated_csv.seek(0)
        
        return StreamingResponse(
            updated_csv,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={file.filename.rsplit('.', 1)[0]}_standardized.csv"}
        )
    except Exception as e:
        return {"message": str(e)}
    
@router.get("/database/{node_notation}/ancestors")
async def get_ancestors(node_notation: str):
    try:
        query = """
            MATCH path = (startNode {identifier: $node_notation})-[:SUBCLASS_OF*]->(ancestor)
            WHERE NOT (ancestor)-[:SUBCLASS_OF]->()
            WITH [node IN reverse(nodes(path)) | COALESCE(node.notation, node.identifier)] AS ancestors
            RETURN collect(DISTINCT ancestors) AS unique_ancestors
            """
        with get_neo4j_driver().session() as session:
            result = session.run(query, node_notation=node_notation)
            record = result.single()

            unique_ancestors = record["unique_ancestors"][0]
            unique_ancestors = [ancestor for ancestor in unique_ancestors if ancestor != node_notation]

            return {"ancestors": unique_ancestors}
    except Exception as e:
        return {"message": str(e)}
