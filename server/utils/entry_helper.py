import re
from fastapi import HTTPException, status
import rdflib
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
                MATCH (child {uri: $child_uri}), (parent {uri: $parent_uri})
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

def update_entry_helper(data: dict, parents: list[str], typeOfEntry: str):
    """Update entry for Neo4j database, change node type if necessary, and link to parent (Species, Strain, or Serotype) as SUBCLASS_OF"""
    
    with get_neo4j_driver().session() as session:
        identifier = data['identifier']
        if not identifier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`identifier` is required in data"
            )

        # Check if the identifier exists
        result = session.run(
            """
            MATCH (e {identifier: $identifier}) 
            RETURN e AS e, labels(e) AS oldTypeOfEntry
            """,
            identifier=identifier
        )
        entry = result.single()
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identifier not found")

        old_labels = entry["oldTypeOfEntry"]

        # Ensure we only work with the first label if the node has multiple
        current_label = old_labels[0] if old_labels else None

        
        # If typeOfEntry has changed, update the node's label
        if current_label != typeOfEntry:
            query = f"""
                MATCH (e {{identifier: $identifier}})
                REMOVE e:`{current_label}`
                SET e:`{typeOfEntry}`
            """
            session.run(query, identifier=identifier)

        # Prepare the SET clause to update the node's properties
        update_properties = ", ".join(f"e.{key} = ${key}" for key in data.keys())
        
        # Update the existing node with new properties
        result = session.run(
            f"""
            MATCH (e {{identifier: $identifier}})
            SET {update_properties}
            RETURN e
            """,
            **data
        )
        updated_entry = result.single()

        if not updated_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update entry")
        updated_node = updated_entry["e"]

        # Update parent relationships if provided
        if parents:
            # Remove old parent relationships first
            session.run(
                """
                MATCH (e)-[r:SUBCLASS_OF]->(p)
                WHERE e.identifier = $identifier
                DELETE r
                """,
                identifier=identifier
            )

            # Process new parent relationships
            parent_query = session.run(
                """
                MATCH (p) 
                WHERE p.identifier IN $parents
                RETURN p
                """,
                parents=parents
            )
            parent_nodes = parent_query.values("p")

            # If any of the parent nodes don't exist, raise an error
            if not parent_nodes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"None of the specified parents were found in Species, Strain, or Serotype"
                )

            # Create new parent relationships
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
            "message": "Entry updated successfully",
            "data": {
                "updated_node": {
                    "properties": updated_node,  # Includes all dynamic properties of the node
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
                MATCH (n)
                WHERE toLower(n.prefLabel) = toLower($label) OR 
                    ANY(altLabel IN n.altLabel WHERE toLower(altLabel) = toLower($label))
                RETURN n.identifier AS notation
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
    
def parse_ttl(file_path):
    g = rdflib.Graph()
    g.parse(file_path, format=rdflib.util.guess_format(file_path))
    return g

# Extract all data from the RDF graph
def extract_all_data_icd10cm(graph):
    nodes = defaultdict(lambda: {"uri": None, "properties": defaultdict(list)})
    prefixes = {
        "skos": "http://www.w3.org/2004/02/skos/core#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "umls": "http://bioportal.bioontology.org/ontologies/umls/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "sio": "http://semanticscience.org/ontology/sio.owl#"
    }
    for s, p, o in graph:
        s_str = str(s)
        
        # Ensure that each subject is added once
        if nodes[s_str]["uri"] is None:
            nodes[s_str]["uri"] = s_str
        for prefix_key, prefix_uri in prefixes.items():
            if str(p).startswith(prefix_uri):
                predicate = str(p).replace(prefix_uri, "")
                break
        else:
            predicate = str(p)
        
        if predicate == "notation":
            nodes[s_str]["properties"]['identifier'].append("MPO:"+str(o))
        elif predicate == "identifier":
            nodes[s_str]["properties"][predicate].append(str(o).replace('_', ':', 1))
        else:
            nodes[s_str]["properties"][predicate].append(str(o))
    return nodes