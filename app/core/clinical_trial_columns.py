# FILE: app/core/clinical_trial_columns.py
"""
Official 17-column list for the Clinical Trial module.
Used by: download-template, upload/import parser, and export — so all
three always stay in sync with the same column order and labels.

Only "Protocol Number" is required. Every other column may be left blank
on upload or manual entry.
"""

CLINICAL_TRIAL_COLUMNS = [
    {"field": "protocol_no", "label": "Protocol Number", "required": True},
    {"field": "study_title", "label": "Study Title", "required": False},
    {"field": "phase", "label": "Phase (Roman Numeral)", "required": False},
    {"field": "sponsor_name", "label": "Sponsor Name", "required": False},
    {"field": "sponsor_address", "label": "Sponsor Address", "required": False},
    {"field": "sponsor_contact", "label": "Sponsor Contact Info", "required": False},
    {"field": "cro_name", "label": "CRO Name", "required": False},
    {"field": "cro_address", "label": "CRO Address", "required": False},
    {"field": "cro_contact", "label": "CRO Contact Info", "required": False},
    {"field": "ct_ref_no", "label": "CT Reference Number", "required": False},
    {
        "field": "ip_name",
        "label": "Name of IP/Comparator/Placebo/OM",
        "required": False,
    },
    {"field": "dosage_strength", "label": "Dosage Strength", "required": False},
    {"field": "pharma_form", "label": "Pharmaceutical Form", "required": False},
    {"field": "drug_type", "label": "Type of Drug", "required": False},
    {"field": "il_approval_no", "label": "IL Approval Number", "required": False},
    {
        "field": "il_approval_date",
        "label": "IL Initial Approval Date",
        "required": False,
    },
    {"field": "total_qty_approve", "label": "Total Qty Approved", "required": False},
]

VALID_PHASES = ["I", "II", "III", "IV"]
