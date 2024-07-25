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
    "zoonotic_infectious_disease": "Subset for zoonotic infectious diseases.",

    "clingen": "Disease classes available in the ClinGen resource",
    "disease_grouping": "disease_grouping",
    "do_inheritance_inconsistent": "classes where the corresponding DO term is both AR and AD https://github.com/monarch-initiative/monarch-disease-ontology/issues/406",
    "gard_rare": "GARD rare disease subset",
    "harrisons_view": "harrisons_view",
    "historic_epidemic": "classes representing a historic epidemic",
    "implicit_genetic_in_ordo": "in ORDO this is classified as genetic even though the class is used for non-genetic disorders",
    "inferred_rare": "inferred rare disease subset",
    "merged_class": "this class merges distinct concepts in other resources",
    "metaclass": "A grouping of disease classes. Should be excluded from analysis",
    "mondo_rare": "mondo rare",
    "mostly_harmless": "condition has no severe phenotypes and is harmless or mostly harmless",
    "n_of_one": "N of one",
    "nord_rare": "nord rare",
    "not_a_disease": "classes that do not represent diseases",
    "obsoletion_candidate": "obsoletion candidate",
    "ordo_biological_anomaly": "biological anomaly",
    "ordo_clinical_situation": "particular clinical situation in a disease or syndrome",
    "ordo_clinical_subtype": "clinical subtype",
    "ordo_clinical_syndrome": "clinical syndrome",
    "ordo_disease": "disease",
    "ordo_disorder": "disorder",
    "ordo_etiological_subtype": "etiological subtype",
    "ordo_group_of_disorders": "group of disorders",
    "ordo_histopathological_subtype": "histopathological subtype",
    "ordo_inheritance_inconsistent": "classes where the corresponding ordo term is both AR and AD https://github.com/monarch-initiative/monarch-disease-ontology/issues/406",
    "ordo_malformation_syndrome": "malformation syndrome",
    "ordo_morphological_anomaly": "morphological anomaly",
    "ordo_subtype_of_a_disorder": "subtype of a disorder",
    "orphanet_rare": "orphanet rare",
    "otar": "Disease classes available in the Open Targets resource",
    "other_hierarchy": "A bin for classes that are likely not diseases and may be moved to a separate hierarchy",
    "predisposition": "Diseases that are pre-dispositions to other diseases",
    "prototype_pattern": "Conforms to the prototype design pattern where the classic/type1 form may be confused with the grouping type. See https://github.com/monarch-initiative/monarch-disease-ontology/issues/149",
    "rare": "rare",
    "rare_grouping": "rare grouping",
    "speculative": "A hypothesized disease whose existence is speculative"
}

subset_definitions_instance = SubsetDefinitions(definitions=subset_definitions)