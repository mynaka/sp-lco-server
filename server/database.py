# database.py

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import sys

# Load environment variables from .env file
load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
AUTH = (USER, PASSWORD)

def get_neo4j_driver():
    if not URI or not USER or not PASSWORD:
        raise ValueError("One or more environment variables are not set: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
    return GraphDatabase.driver(URI, auth=AUTH)