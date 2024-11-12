from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class Entry(BaseModel):
    name: str
    term_code: str  # format: <source>:<idnumber> (unique)
    elements: Dict[str, Any]
    associated_terms: Dict[str, List[str]]  # {"relationship": [Term Codes]}

class Definition(BaseModel):
    val: str
    xrefs: List[str]

class Synonym(BaseModel):
    pred: str
    val: str

class Xref(BaseModel):
    val: str

class BasicPropertyValue(BaseModel):
    pred: str
    val: str

class Meta(BaseModel):
    definition: Optional[Definition] = None
    subsets: Optional[List[str]] = None
    synonyms: Optional[List[Synonym]] = None
    xrefs: Optional[List[Xref]] = None
    basicPropertyValues: List[BasicPropertyValue]

class Edge(BaseModel):
    sub: str
    pred: str
    obj: str

class DOTermData(BaseModel):
    id: str
    lbl: str
    type: str
    meta: Meta
    edges: Optional[List[Edge]] = None

class DataInput(BaseModel):
    prefLabel: str
    identifier: str
    description: str
    format: str
    sample: str
    output: str

class DataInputSpecies(BaseModel):
    identifier: str
    prefLabel: str
    altLabel: Optional[list[str]] = None
    refs: Optional[list[str]] = None

class DataInputProtein(BaseModel):
    identifier: str
    prefLabel: str
    function: str
    altLabel: Optional[list[str]] = None
    features: str
    sequence: str
    refs: Optional[list[str]] = None