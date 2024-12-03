import re
from fastapi import HTTPException

from models.entry_model import DOTermData
from models.subset import subset_definitions_instance

from  utils.entry_helper import query_icd10cm_neo4j
def process_row(row):
    """
    Process a single row by querying notation for each cell.
    """
    for i in range(len(row)):
        label = row[i] 
        notation = query_icd10cm_neo4j(label)
        
        if notation:
            row[i] = notation
    return row