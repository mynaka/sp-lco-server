import re
from fastapi import HTTPException, status
from rdflib import Graph, Namespace
from database import get_neo4j_driver
from collections import defaultdict

from models.entry_model import DataInputSpecies, DataInputProtein

def create_nodes(nodes):
    relations_to_create = []

    with get_neo4j_driver().session() as session:
        for node_uri, data in nodes.items():
            properties = {k: v if len(v) > 1 else v[0] for k, v in data["properties"].items() if k != "subClassOf"}

            # Create or update the node
            session.run(
                """
                MERGE (entity:Term {uri: $uri})
                ON CREATE SET entity += $properties
                """,
                uri=node_uri,
                properties=properties
            )

            if "subClassOf" in data["properties"]:
                for superclass_uri in data["properties"]["subClassOf"]:
                    relations_to_create.append((node_uri, superclass_uri))

    # Now create the stored relationships
    with get_neo4j_driver().session() as session:
        for node_uri, superclass_uri in relations_to_create:
            session.run(
                """
                MATCH (child {uri: $child_uri}), (parent:Entity {uri: $parent_uri})
                MERGE (child)-[:SUBCLASS_OF]->(parent)
                """,
                child_uri=node_uri,
                parent_uri=superclass_uri
            )
    
def create_entry_helper(data: dict, parents: list[str], typeOfEntry: str):
    """Create entry for Neo4j database and link to parent (Species, Strain, or Serotype) as SUBCLASS_OF"""
    
    with get_neo4j_driver().session() as session:
        identifier = data['identifier']
        if not identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`identifier` is required in data"
            )

        # Check if the identifier already exists
        result = session.run(
            "MATCH (e {identifier: $identifier}) RETURN e",
            identifier=data["identifier"]
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier already exists")

        # Search for the parent nodes (can be Species, Strain, or Serotype)
        if not parents:
            parent_nodes = []
        else:
            parent_query = session.run(
                """
                MATCH (p) 
                WHERE p.identifier IN $parents
                RETURN p
                """,
                parents=parents
            )
            parent_nodes = parent_query.values("p")

            # If all parent nodes don't exist, raise an error
            if not parent_nodes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"None of the specified parents were found in Species, Strain, or Serotype"
                )
        

        # Create the new node entry
        properties = ", ".join(f"{key}: ${key}" for key in data.keys())
        result = session.run(
            f"""
            CREATE (e:{typeOfEntry} {{ {properties} }})
            RETURN e
            """,
            **data
        )
        created_entry = result.single()

        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")
        created_node = created_entry["e"]

        # Process parent relationships
        for parent in parents:
            session.run(
                """
                MATCH (e), (p)
                WHERE e.identifier = $identifier AND p.identifier = $parent
                CREATE (e)-[:SUBCLASS_OF]->(p)
                """,
                identifier=identifier,
                parent=parent
            )

        # Update stuff for searching
        try:
            session.run("DROP INDEX entityLabelIndex IF EXISTS;")
            session.run(
                """
                MATCH (n)
                WHERE NOT 'AllNodes' IN labels(n) AND NOT 'User' IN labels(n)
                SET n:AllNodes
                """
            )
            session.run(
                """
                CREATE FULLTEXT INDEX entityLabelIndex FOR (n:AllNodes)
                ON EACH [n.prefLabel, n.altLabel, n.identifier];
                """
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to run maintenance commands: {str(e)}"
            )
        
        return {
            "status": "success",
            "code": 200,
            "message": "Entry created successfully",
            "data": {
                "created_node": {
                    "properties": created_node,  # Includes all dynamic properties of the node
                },
                "relationships": {
                    "type": "SUBCLASS_OF",
                    "parents": parents if parents else "No parents linked"
                }
            }
        }

def query_icd10cm_neo4j(label):
    """
    Get the standardized notation of a label or alternate label within an ontology.
    """
    try:
        with get_neo4j_driver().session() as session:
            result = session.run(
                """
                MATCH (n:Entity)
                WHERE n.prefLabel = $label OR ANY(altLabel IN n.altLabel WHERE altLabel = $label)
                RETURN COALESCE(n.notation, n.identifier) AS notation
                """,
                label=label
            )
            record = result.single()
            if record:
                return record["notation"]
            else:
                return None
    except Exception as e:
        return {"status": "500", "error": str(e)}