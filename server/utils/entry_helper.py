from fastapi import HTTPException, status
import rdflib
from database import get_neo4j_driver
from collections import defaultdict

from models.entry_model import DataInputSpecies, DataInputProtein

def determine_database(code: str) -> str:
    """Determine the database based on the code prefix."""
    return code.split(":")[0].lower()

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
            nodes[s_str]["properties"][predicate].append("ICD10CM:"+str(o))
        elif predicate == "identifier":
            nodes[s_str]["properties"][predicate].append(str(o).replace('_', ':', 1))
        else:
            nodes[s_str]["properties"][predicate].append(str(o))
    return nodes


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

def create_nodes(nodes):
    relations_to_create = []

    with get_neo4j_driver().session() as session:
        for node_uri, data in nodes.items():
            properties = {k: v if len(v) > 1 else v[0] for k, v in data["properties"].items() if k != "subClassOf"}

            # Create or update the node
            session.run(
                """
                MERGE (entity:Entity {uri: $uri})
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

def create_species(data: DataInputSpecies):
    """Create entry for Neo4j database"""
    
    with get_neo4j_driver().session() as session:
        # Check if the identifier already exists
        result = session.run(
            "MATCH (e:Species {identifier: $identifier}) RETURN e",
            identifier=data.identifier
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier already exists")

        # Create the entry node
        result = session.run(
            """
            CREATE (e:Species {prefLabel: $prefLabel, identifier: $identifier, altLabel: $altLabel, refs: $refs})
            RETURN e
            """,
            identifier=data.identifier,
            prefLabel=data.prefLabel,
            altLabel=data.altLabel,
            refs=data.refs
        )
        created_entry = result.single()
        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")

        # Extract data from the created entry
        node = created_entry["e"]
        return {
            "status": 200,
            "term": {
                "name": node["prefLabel"],
                "identifier": node["identifier"],
                "altLabel": node["altLabel"],
                "refs": node["refs"]
            }
        }
    
    
def create_strain_serotype(data: DataInputSpecies, parent: str, typeOfEntry: str):
    """Create entry for Neo4j database and link to parent (Species, Strain, or Serotype) as SUBCLASS_OF"""
    
    with get_neo4j_driver().session() as session:
        # Check if the identifier already exists
        result = session.run(
            "MATCH (e {identifier: $identifier}) RETURN e",
            identifier=data.identifier
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier already exists")

        # Search for the parent node (it could be a Species, Strain, or Serotype)
        parent_result = session.run(
            """
            MATCH (p) WHERE p.identifier = $parent AND (p:Species OR p:Strain OR p:Serotype)
            RETURN p
            """,
            parent=parent
        )
        parent_node = parent_result.single()

        # If parent node doesn't exist, raise an error
        if not parent_node:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Parent {parent} not found in Species, Strain, or Serotype")

        # Create the new strain or serotype entry
        result = session.run(
            f"""
            CREATE (e:{typeOfEntry} {{prefLabel: $prefLabel, identifier: $identifier, altLabel: $altLabel, refs: $refs}})
            RETURN e
            """,
            identifier=data.identifier,
            prefLabel=data.prefLabel,
            altLabel=data.altLabel,
            refs=data.refs
        )
        created_entry = result.single()

        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")

        created_node = created_entry["e"]
        session.run(
            """
            MATCH (e), (p)
            WHERE e.identifier = $identifier AND p.identifier = $parent
            CREATE (e)-[:SUBCLASS_OF]->(p)
            """,
            identifier=data.identifier,
            parent=parent
        )

        # Return the newly created entry and link information
        return {
            "status": 200,
            "term": {
                "name": created_node["prefLabel"],
                "identifier": created_node["identifier"],
                "altLabel": created_node["altLabel"],
                "refs": created_node["refs"]
            }
        }
    
def create_protein_gene(data: DataInputProtein, parent: str, typeOfEntry: str):
    """Create entry for Neo4j database and link to parent (Species, Strain, or Serotype) as SUBCLASS_OF"""
    
    with get_neo4j_driver().session() as session:
        # Check if the identifier already exists
        result = session.run(
            "MATCH (e {identifier: $identifier}) RETURN e",
            identifier=data.identifier
        )
        if result.single():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identifier already exists")

        # Search for the parent node (it could be a Species, Strain, or Serotype)
        parent_result = session.run(
            """
            MATCH (p) WHERE p.identifier = $parent AND (p:Species OR p:Strain OR p:Serotype)
            RETURN p
            """,
            parent=parent
        )
        parent_node = parent_result.single()

        # If parent node doesn't exist, raise an error
        if not parent_node:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Parent {parent} not found in Species, Strain, or Serotype")

        # Create the new strain or serotype entry
        result = session.run(
            f"""
            CREATE (e:{typeOfEntry} 
                {{prefLabel: $prefLabel,
                identifier: $identifier,
                function: $function,
                altLabel: $altLabel,
                features: $features,
                sequence: $sequence,
                refs: $refs}})
            RETURN e
            """,
            identifier=data.identifier,
            prefLabel=data.prefLabel,
            function=data.function,
            altLabel=data.altLabel,
            features=data.features,
            sequence=data.sequence,
            refs=data.refs
        )
        created_entry = result.single()

        if not created_entry:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create entry")

        created_node = created_entry["e"]
        session.run(
            """
            MATCH (e), (p)
            WHERE e.identifier = $identifier AND p.identifier = $parent
            CREATE (e)-[:SUBCLASS_OF]->(p)
            """,
            identifier=data.identifier,
            parent=parent
        )

        # Return the newly created entry and link information
        return {
            "status": 200,
            "term": {
                "name": created_node["prefLabel"],
                "identifier": created_node["identifier"],
                "altLabel": created_node["altLabel"],
                "refs": created_node["refs"]
            }
        }