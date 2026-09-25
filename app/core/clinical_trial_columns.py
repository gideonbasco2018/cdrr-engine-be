# FILE: app/core/clinical_trial_columns.py
"""
Column definitions for the Clinical Trial module, now split across two
tables:
  - CLINICAL_TRIAL_COLUMNS: the "1" side (clinical_trials table)
  - CLINICAL_TRIAL_DRUG_COLUMNS: the "many" side (clinical_trial_drugs table)

The Excel template/upload/export keep the same 17-column flat layout for
usability — a trial with multiple drugs is represented as multiple rows
sharing the same trial-level values (merged cells in practice), grouped
back into one trial + N drugs on parse.
"""

CLINICAL_TRIAL_COLUMNS = [
    {"field": "protocol_no", "label": "Protocol Number", "required": False},
    {"field": "study_title", "label": "Study Title", "required": False},
    {"field": "phase", "label": "Phase (Roman Numeral)", "required": False},
    {"field": "sponsor_name", "label": "Sponsor Name", "required": False},
    {"field": "sponsor_address", "label": "Sponsor Address", "required": False},
    {"field": "sponsor_contact", "label": "Sponsor Contact Info", "required": False},
    {"field": "cro_name", "label": "CRO Name", "required": False},
    {"field": "cro_address", "label": "CRO Address", "required": False},
    {"field": "cro_contact", "label": "CRO Contact Info", "required": False},
    {"field": "ct_ref_no", "label": "CT Reference Number", "required": False},
    {"field": "il_approval_no", "label": "IL Approval Number", "required": False},
    {
        "field": "il_approval_date",
        "label": "IL Initial Approval Date",
        "required": False,
    },
]

CLINICAL_TRIAL_DRUG_COLUMNS = [
    {
        "field": "ip_name",
        "label": "Name of IP/Comparator/Placebo/OM",
        "required": False,
    },
    {"field": "dosage_strength", "label": "Dosage Strength", "required": False},
    {"field": "pharma_form", "label": "Pharmaceutical Form", "required": False},
    {"field": "drug_type", "label": "Type of Drug", "required": False},
    {"field": "total_qty_approve", "label": "Total Qty Approved", "required": False},
]

# Excel template/upload/export must keep the ORIGINAL 17-column visual
# order, even though the fields are now split across two tables:
#   Protocol No, Study Title, Phase, Sponsor (3), CRO (3), CT Ref No,
#   [drug fields: IP Name, Dosage, Pharma Form, Drug Type],
#   IL Approval No, IL Approval Date, [drug field: Total Qty Approved]
#
# Note Total Qty Approved sits at the very end, separated from the other
# drug fields — so this can't be built by simply concatenating
# CLINICAL_TRIAL_COLUMNS + CLINICAL_TRIAL_DRUG_COLUMNS. Whether a field is
# trial-level or drug-level is still determined by membership in those
# two lists (parsing is field-name based, not position based), so this
# reordering doesn't affect parse_upload_workbook's grouping logic at all.
_column_lookup = {
    c["field"]: c for c in CLINICAL_TRIAL_COLUMNS + CLINICAL_TRIAL_DRUG_COLUMNS
}

ALL_EXCEL_COLUMNS = [
    _column_lookup["protocol_no"],
    _column_lookup["study_title"],
    _column_lookup["phase"],
    _column_lookup["sponsor_name"],
    _column_lookup["sponsor_address"],
    _column_lookup["sponsor_contact"],
    _column_lookup["cro_name"],
    _column_lookup["cro_address"],
    _column_lookup["cro_contact"],
    _column_lookup["ct_ref_no"],
    _column_lookup["ip_name"],
    _column_lookup["dosage_strength"],
    _column_lookup["pharma_form"],
    _column_lookup["drug_type"],
    _column_lookup["il_approval_no"],
    _column_lookup["il_approval_date"],
    _column_lookup["total_qty_approve"],
]

VALID_PHASES = [
    "I",
    "II",
    "III",
    "IV",
    "I/II",
    "II/III",
    "III/IV",
    "I/II/III",
    "Others",
]
