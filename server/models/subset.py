from pydantic import BaseModel
from typing import Dict, Optional

# Define the Pydantic model
class SubsetDefinitions(BaseModel):
    definitions: Dict[str, str]

    def get_definition(self, subset_id: str) -> Optional[str]:
        return self.definitions.get(subset_id, subset_id)

# Subset definitions dictionary
subset_definitions = {
    "DO_AGR_slim": "Subset for the Alliance of Genome Resources.",
    "DO_cancer_slim": "A subset focused on cancer terms.",
    "DO_CFDE_slim": "Subset for the CFDE (Common Fund Data Ecosystem).",
    "DO_FlyBase_slim": "Subset for FlyBase, a database of Drosophila genes and genomes.",
    "DO_GXD_slim": "Subset for the Gene Expression Database.",
    "DO_IEDB_slim": "Subset for the Immune Epitope Database.",
    "DO_infectious_disease_slim": "Subset focusing on infectious diseases.",
    "DO_MGI_slim": "Subset for the Mouse Genome Informatics database.",
    "DO_RAD_slim": "Subset for rare diseases.",
    "DO_rare_slim": "Another subset focused on rare diseases.",
    "GOLD": "Genomes OnLine Database subset.",
    "gram-negative_bacterial_infectious_disease": "Subset for gram-negative bacterial infectious diseases.",
    "gram-positive_bacterial_infectious_disease": "Subset for gram-positive bacterial infectious diseases.",
    "NCIthesaurus": "National Cancer Institute Thesaurus subset.",
    "sexually_transmitted_infectious_disease": "Subset for sexually transmitted infectious diseases.",
    "tick-borne_infectious_disease": "Subset for tick-borne infectious diseases.",
    "TopNodes_DOcancerslim": "Subset for top nodes in the cancer slim.",
    "zoonotic_infectious_disease": "Subset for zoonotic infectious diseases."
}

subset_definitions_instance = SubsetDefinitions(definitions=subset_definitions)