# app/core/eservices_drug_groups.py
from typing import Dict, List, TypedDict


class DrugGroup(TypedDict):
    label: str
    category_keywords: List[str]
    generic_name_keywords: List[str]
    # Maps a cleaned, lowercase misspelled generic name to its correct name.
    name_aliases: Dict[str, str]
    # True: one row per category and generic name. False: one row per category.
    group_by_generic_name: bool
    # True: order by application count first. False: order by category first.
    sort_count_first: bool


# Add a new entry here to support a new drug group.
# Keywords are matched using LIKE '%keyword%'.
DRUG_GROUPS: Dict[str, DrugGroup] = {
    "tuberculosis": {
        "label": "Tuberculosis",
        "category_keywords": [
            "Antimycobacterial",
            "Antituberculosis",
            "Anti-Tb",
            "Tuberculosis",
        ],
        "generic_name_keywords": [
            "Moxifloxacin",
            "Linezolid",
            "Rifampicin",
            "Isoniazid",
            "Ethambutol",
            "Pyrazinamide",
        ],
        "name_aliases": {
            "linezolid lid": "Linezolid",
        },
        "group_by_generic_name": True,
        "sort_count_first": False,
    },
    "cancer": {
        "label": "Cancer",
        "category_keywords": [
            "antineoplastic",
            "antifolate",
            "tyrosine-kinase inhibitor",
            "tyrosine kinase inhibitor",
        ],
        "generic_name_keywords": [],
        "name_aliases": {},
        "group_by_generic_name": False,
        "sort_count_first": True,
    },
}
