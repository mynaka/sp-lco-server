import rdflib
from database import get_neo4j_driver
from collections import defaultdict
from urllib.parse import urlparse

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

# Neo4j Loader Class to create consolidated nodes
class Neo4jLoader:
    def __init__(self):
        self.driver = get_neo4j_driver()
    
    def close(self):
        self.driver.close()
    
    # Load extracted data into Neo4j as nodes
    def create_nodes(self, nodes):
        relations_to_create = []  # List to hold relationships to create later

        with self.driver.session() as session:
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

                # Handle subClassOf relationships
                if "subClassOf" in data["properties"]:
                    for superclass_uri in data["properties"]["subClassOf"]:
                        # Store the relation in the array for later processing
                        relations_to_create.append((node_uri, superclass_uri))

        # Now create the stored relationships
        with self.driver.session() as session:
            for node_uri, superclass_uri in relations_to_create:
                session.run(
                    """
                    MATCH (child:Entity {uri: $child_uri}), (parent:Entity {uri: $parent_uri})
                    MERGE (child)-[:SUBCLASS_OF]->(parent)
                    """,
                    child_uri=node_uri,
                    parent_uri=superclass_uri
                )
    
    def query_icd10cm_neo4j(self, label):
        """
        Get the standardized notation of a label or alternate label within an ontology.
        """
        try:
            with self.driver.session() as session:
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