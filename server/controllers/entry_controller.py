# controllers/entry_controller.py
import csv
from io import StringIO
from typing import List, Optional
from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile, status, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from concurrent.futures import ProcessPoolExecutor

from database import get_neo4j_driver

#Models
from models.entry_model import DataInput, DataInputProtein

#Utilities
from utils.auth import get_current_user
from utils.entry_helper import *
from utils.file_helper import *

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/create")
async def create_entry(
    data: dict = Body(...),
    parents: list[str] = Body([]),
    typeOfEntry: str = Body(...),
    current_user: dict = Depends(get_current_user)
):
    # Call the create_protein_gene function in a thread pool
    result = await run_in_threadpool(create_entry_helper, data, parents, typeOfEntry)
    return {"status": "200", "result": result}

@router.put("/update")
async def update_entry(
    data: dict = Body(...),
    parents: Optional[List[str]] = Body([]),
    typeOfEntry: str = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing entry and its relationships in the Neo4j database.
    """
    # Ensure the identifier is present in the input data
    identifier = data.get("identifier")
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`identifier` is required in the data payload."
        )

    try:
        result = await run_in_threadpool(update_entry_helper, data, parents, typeOfEntry)
        return {"status": "success", "result": result}
    except HTTPException as e:
        # Forward HTTP exceptions raised in the helper
        raise e
    except Exception as e:
        # Catch unexpected exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.get("/all")
async def get_all_entries():
    """Get all existing entries from all databases.

    Returns names and codes of all entries. Used for Landing Page Search Bar.
    """
    try:
        with get_neo4j_driver().session() as session:
            result = session.run(
                """
                MATCH (e)
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
async def search_entries(searchQuery: str, selectedNodes: list[str] = Query(default=[])):
    """
    Search for the 10 closest terms to the provided query in Entity nodes based on prefLabel and altLabel,
    excluding nodes with identifiers in the selectedNodes list.
    """
    try:
        with get_neo4j_driver().session() as session:
            result = session.run(
                """
                CALL db.index.fulltext.queryNodes('entityLabelIndex', $query)
                YIELD node, score
                WHERE 
                    (node.notation IS NOT NULL OR node.identifier IS NOT NULL) AND
                    NOT COALESCE(node.notation, node.identifier) IN $excludeNodes
                RETURN node.prefLabel AS name, 
                       COALESCE(node.notation, node.identifier) AS term_code, 
                       score
                ORDER BY score DESC
                LIMIT 10
                """,
                {"query": searchQuery, "excludeNodes": selectedNodes}
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
            WHERE (e.notation STARTS WITH $database + ":" OR e.identifier STARTS WITH $database + ":") AND 
                NOT((e)-[]->())
            RETURN e.prefLabel AS prefLabel, 
                COALESCE(e.notation, e.identifier) AS notation,
                EXISTS(()-[]->(e)) AS hasIncomingRelationships,
                e AS data,
                labels(e) AS nodeLabel
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
                node_type = record["nodeLabel"]
                
                # Create entry data
                entry_data = {
                    "key": notation,
                    "label": pref_label,
                    "data": entry,
                    "leaf": not has_incoming_relationships,
                    "loading": True,
                    "nodeType": node_type[1] if node_type[0] == "AllNodes" else node_type[0]
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
        WHERE (parent.identifier = $node_notation OR parent.notation = $node_notation)
        WITH child, labels(child) AS nodeLabel
        MATCH (child)-[:SUBCLASS_OF]->(allParents)
        RETURN 
            EXISTS(()-[]->(child)) AS hasIncomingRelationships,
            nodeLabel AS nodeLabel,
            child AS data,
            collect({ name: allParents.prefLabel, code: allParents.identifier }) AS parents
    """
    with get_neo4j_driver().session() as session:
        result = session.run(query, node_notation=node_notation)

        children_entries = [
            {
                "key": record["data"]["identifier"],
                "label": record["data"]["prefLabel"],
                "data": record["data"],
                "leaf": not record["hasIncomingRelationships"],
                "loading": True,
                "nodeType": record["nodeLabel"][1] if record["nodeLabel"][0] == "AllNodes" else record["nodeLabel"][0],
                "parents": record["parents"]
            }
            for record in result
        ]
        return {"status": "200", "entries": children_entries}

@router.on_event("shutdown")
async def shutdown_event():
    get_neo4j_driver().close()

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
    
@router.post("/load_ontology")
async def load_ontology(file_path: str = Form(...)):
    try:
        rdf_graph = parse_ttl(file_path)
        triples = extract_all_data_icd10cm(rdf_graph)
        create_nodes(triples)
        return {"message": "Ontology loaded successfully"}
    except:
        return {"message": file_path}