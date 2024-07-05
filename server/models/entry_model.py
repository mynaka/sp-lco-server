from pydantic import BaseModel
from typing import List, Dict, Any

class Entry(BaseModel):
    name: str
    term_code: str  # format: <source>:<idnumber> (unique)
    elements: Dict[str, Any]
    associated_terms: Dict[str, List[str]]  # {"relationship": [Term Codes]}