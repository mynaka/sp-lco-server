# database.py

import sys
from neo4j import GraphDatabase


URI = "neo4j+s://a7ba9f08.databases.neo4j.io"
AUTH = ("neo4j", "QDv01qBPkFV9tV_RT-DnMYWRGZEL7a3bo2zMI1MvGbk")

def get_neo4j_driver():
    return GraphDatabase.driver(URI, auth = AUTH)
