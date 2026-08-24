# app/schemas/gmp_record.py
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from typing import Optional, List
from datetime import datetime, date
from dateutil import parser as dateutil_parser


# ─────────────────────────────────────────────────────────────────────────────
# Flexible date/datetime coercion
# ─────────────────────────────────────────────────────────────────────────────
# Accepts a date/datetime object, or a string in virtually any common format
# (MM/DD/YYYY, DD-MM-YYYY, "January 5, 2025", ISO, etc.) and normalizes it.
# Used as a `mode="before"` validator on every date-like field in this file so
# the API never rejects a request just because the date wasn't already
# YYYY-MM-DD — it converts automatically instead.
def _coerce_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        return dateutil_parser.parse(s, fuzzy=True).date()
    raise ValueError(f"Unrecognized date value: {v!r}")


def _coerce_datetime(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        return dateutil_parser.parse(s, fuzzy=True)
    raise ValueError(f"Unrecognized datetime value: {v!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Field Audit Log
# ─────────────────────────────────────────────────────────────────────────────
class GMPFieldAuditLogResponse(BaseModel):
    id: int
    gmp_record_id: int
    field_name: str
    field_label: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    action_type: str
    gmp_log_id: Optional[int] = None
    step_context: Optional[str] = None
    session_id: str
    user_name: Optional[str] = None
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Application Logs
# ─────────────────────────────────────────────────────────────────────────────
class GMPApplicationLogResponse(BaseModel):
    id: int
    gmp_record_id: int
    application_step: Optional[str] = None
    user_name: Optional[str] = None
    user_id: Optional[int] = None
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    start_date: Optional[datetime] = None
    accomplished_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    del_index: Optional[int] = None
    del_previous: Optional[int] = None
    del_last_index: Optional[int] = None
    del_thread: Optional[str] = None
    is_read: Optional[int] = None
    is_starred: Optional[int] = None
    is_received: Optional[int] = None
    received_at: Optional[datetime] = None
    received_by: Optional[str] = None
    # ── Extended fields ──────────────────────────────────────────────────────
    action_type: Optional[str] = None
    decision_result: Optional[str] = None
    decision_authority_id: Optional[int] = None
    decision_authority_name: Optional[str] = None
    # Overrides the default "COMPLETED" status written to the log being
    # closed — e.g. "RELEASED" for the OD Releasing step's final action.
    # Leave unset for every ordinary advance; only steps that end the
    # workflow with a status other than plain "COMPLETED" need to pass this.
    completion_status: Optional[str] = None
    # Overrides the default "COMPLETED" status written to the log being
    # closed — e.g. "RELEASED" for the OD Releasing step's final action.
    # Leave unset for every ordinary advance; only steps that end the
    # workflow with a status other than plain "COMPLETED" need to pass this.
    completion_status: Optional[str] = None
    doctrack_remarks: Optional[str] = None
    deadline_date: Optional[datetime] = None
    working_days: Optional[int] = None
    # ── Sent-by tracking ─────────────────────────────────────────────────────
    sent_by_user_id: Optional[int] = None
    sent_by_user_name: Optional[str] = None
    sent_by_full_name: Optional[str] = None
    sent_by_alias: Optional[str] = None
    # reassignment
    reassigned_by_user_id: Optional[int] = None
    reassigned_by_user_name: Optional[str] = None
    reassigned_at: Optional[datetime] = None
    reassigned_from_user_id: Optional[int] = None
    reassigned_from_user_name: Optional[str] = None
    reassigned_to_user_id: Optional[int] = None
    reassigned_to_user_name: Optional[str] = None
    reassignment_reason: Optional[str] = None
    reassignment_remarks: Optional[str] = None
    # reroute
    rerouted_by_user_id: Optional[int] = None
    rerouted_by_user_name: Optional[str] = None
    rerouted_at: Optional[datetime] = None
    reroute_from_step: Optional[str] = None
    reroute_target_step: Optional[str] = None
    reroute_reason: Optional[str] = None
    reroute_remarks: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Advance Step request body
# ─────────────────────────────────────────────────────────────────────────────
class GMPAdvanceStepRequest(BaseModel):
    current_step: str
    action: str
    recommendation: str = ""
    remarks: str = ""
    doctrack_remarks: str = ""
    next_assignee_name: Optional[str] = None
    next_assignee_id: Optional[int] = None
    action_type: Optional[str] = None
    decision_result: Optional[str] = None
    decision_authority_id: Optional[int] = None
    decision_authority_name: Optional[str] = None
    completion_status: Optional[str] = None
    # Was `Optional[str]`, manually parsed via `datetime.fromisoformat` in the
    # route handler (which threw on anything but strict ISO format). Now a
    # real datetime with flexible parsing, so any format the caller sends is
    # normalized automatically instead of erroring.
    deadline_date: Optional[datetime] = None
    working_days: Optional[int] = None

    @field_validator("deadline_date", mode="before")
    @classmethod
    def _parse_deadline_date(cls, v):
        return _coerce_datetime(v)


# ─────────────────────────────────────────────────────────────────────────────
# Update log request body (for completing / editing an open log)
# ─────────────────────────────────────────────────────────────────────────────
class GMPApplicationLogUpdate(BaseModel):
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    doctrack_remarks: Optional[str] = None
    # Was `Optional[str]`, manually parsed via `datetime.fromisoformat` in the
    # route handler with a bare `except ValueError: pass` (silently *keeping
    # the original unparsed string* on failure, which would then hit the DB
    # as garbage). Now a real datetime, flexibly parsed here instead.
    accomplished_date: Optional[datetime] = None
    del_last_index: Optional[int] = None
    del_thread: Optional[str] = None
    action_type: Optional[str] = None
    decision_result: Optional[str] = None
    decision_authority_id: Optional[int] = None
    decision_authority_name: Optional[str] = None

    @field_validator("accomplished_date", mode="before")
    @classmethod
    def _parse_accomplished_date(cls, v):
        return _coerce_datetime(v)


# ─────────────────────────────────────────────────────────────────────────────
# Reassign request body
# ─────────────────────────────────────────────────────────────────────────────
class GMPReassignRequest(BaseModel):
    application_step: str
    reassigned_to_user_name: str
    reassigned_to_user_id: Optional[int] = None
    reassignment_reason: Optional[str] = None
    reassignment_remarks: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Reroute request body
# ─────────────────────────────────────────────────────────────────────────────
class GMPRerouteRequest(BaseModel):
    reroute_from_step: str
    reroute_target_step: str
    target_user_name: Optional[str] = None
    target_user_id: Optional[int] = None
    reroute_reason: Optional[str] = None
    reroute_remarks: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Add Issuance request body
# ─────────────────────────────────────────────────────────────────────────────
class GMPAddIssuanceRequest(BaseModel):
    type_of_issuance: str


class GMPReopenRequest(BaseModel):
    related_dtn: str


class GMPIssuanceFieldsUpdate(BaseModel):
    type_of_issuance: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_validity: Optional[str] = None
    secpa_number: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Task response (log + embedded record fields)
# ─────────────────────────────────────────────────────────────────────────────
class GMPTaskRecordEmbed(BaseModel):
    GMP_ID: int
    GMP_DTN: Optional[int] = None
    GMP_RELATED_DTN: Optional[str] = None
    GMP_DATE_RECEIVED: Optional[date] = None
    GMP_LTO_COMPANY: Optional[str] = None
    GMP_LTO_NUMBER: Optional[str] = None
    GMP_LTO_ADDRESS: Optional[str] = None
    GMP_TRANSACTION_TYPE: Optional[str] = None
    GMP_EST_CATEGORY: Optional[str] = None
    GMP_FOREIGN_MANUFACTURER: Optional[str] = None
    GMP_FOREIGN_MANUFACTURER_ADDRESS: Optional[str] = None
    GMP_SECPA_NUMBER: Optional[str] = None
    GMP_CERTIFICATE_NUMBER: Optional[str] = None
    GMP_TYPE_OF_ISSUANCE: Optional[str] = None
    GMP_CERTIFICATE_VALIDITY: Optional[str] = None
    GMP_DECISION: Optional[str] = None
    GMP_APP_STATUS: Optional[str] = None
    GMP_RELEASED_DATE: Optional[date] = None
    GMP_PROCESSED_TIME: Optional[str] = None
    GMP_END_DATE: Optional[date] = None
    GMP_TIMELINE: Optional[str] = None
    GMP_REMARKS: Optional[str] = None
    GMP_NOD_DATE_1: Optional[date] = None
    GMP_NOD_DATE_2: Optional[date] = None
    GMP_NOD_DATE_3: Optional[date] = None
    GMP_NOD_DATE_4: Optional[date] = None
    GMP_NOD_DATE_5: Optional[date] = None
    GMP_DATE_PRINTED: Optional[date] = None
    GMP_COMPLIANCE_DOCS_DATE_RECEIVED: Optional[date] = None
    GMP_PRODUCT_LINE: Optional[str] = None
    GMP_CURRENT_STEP: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class GMPTaskResponse(BaseModel):
    id: int
    gmp_record_id: int
    application_step: Optional[str] = None
    user_name: Optional[str] = None
    user_id: Optional[int] = None
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    start_date: Optional[datetime] = None
    accomplished_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    del_index: Optional[int] = None
    del_previous: Optional[int] = None
    del_last_index: Optional[int] = None
    del_thread: Optional[str] = None
    is_read: Optional[int] = None
    is_starred: Optional[int] = None
    is_received: Optional[int] = None
    received_at: Optional[datetime] = None
    received_by: Optional[str] = None
    action_type: Optional[str] = None
    decision_result: Optional[str] = None
    decision_authority_id: Optional[int] = None
    decision_authority_name: Optional[str] = None
    doctrack_remarks: Optional[str] = None
    sent_by_user_id: Optional[int] = None
    sent_by_user_name: Optional[str] = None
    sent_by_full_name: Optional[str] = None
    sent_by_alias: Optional[str] = None
    deadline_date: Optional[datetime] = None
    working_days: Optional[int] = None
    gmp_record: Optional[GMPTaskRecordEmbed] = None
    # Every distinct Type of Issuance across all GMPRecord siblings sharing
    # this task's DTN (added via Add Issuance) — not just gmp_record's own
    # single value, since siblings never carry their own task/log. Populated
    # in get_tasks_for_user via one bulk query, not a model relationship.
    all_issuance_types: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class GMPTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[GMPTaskResponse]


# ─────────────────────────────────────────────────────────────────────────────
# Delegation
# ─────────────────────────────────────────────────────────────────────────────
# Aligned to app/models/gmp_record.py's GMPDelegation:
#   GMP_QUALITY_EVALUATOR* -> GMP_EVALUATOR*   ("Quality Evaluator" -> "Evaluator")
#   GMP_DECKER_2*          -> GMP_QA_ADMIN*    (2nd-pass decker slot -> QA Admin)
#   GMP_QA_SUPERVISOR*     removed             (QA Supervisor group deleted)
#   GMP_DECKER_3*          removed             (unused 3rd-pass decker slot)
class GMPDelegationResponse(BaseModel):
    GMP_DECKER_1: Optional[str] = None
    GMP_DECKER_1_DECISION: Optional[str] = None
    GMP_DECKER_1_REMARKS: Optional[str] = None
    GMP_DATE_DECKER_1_END: Optional[datetime] = None
    GMP_EVALUATOR: Optional[str] = None
    GMP_EVALUATOR_DECISION: Optional[str] = None
    GMP_EVALUATOR_REMARKS: Optional[str] = None
    GMP_DATE_EVALUATOR_END: Optional[datetime] = None
    GMP_CHECKER: Optional[str] = None
    GMP_CHECKER_DECISION: Optional[str] = None
    GMP_CHECKER_REMARKS: Optional[str] = None
    GMP_DATE_CHECKER_END: Optional[datetime] = None
    GMP_QA_ADMIN: Optional[str] = None
    GMP_QA_ADMIN_DECISION: Optional[str] = None
    GMP_QA_ADMIN_REMARKS: Optional[str] = None
    GMP_DATE_QA_ADMIN_END: Optional[datetime] = None
    GMP_LRD_CHIEF: Optional[str] = None
    GMP_LRD_CHIEF_DECISION: Optional[str] = None
    GMP_LRD_CHIEF_REMARKS: Optional[str] = None
    GMP_DATE_LRD_CHIEF_END: Optional[datetime] = None
    GMP_OD_RECEIVING: Optional[str] = None
    GMP_OD_RECEIVING_DECISION: Optional[str] = None
    GMP_OD_RECEIVING_REMARKS: Optional[str] = None
    GMP_DATE_OD_RECEIVING_END: Optional[datetime] = None
    GMP_OD_RELEASING: Optional[str] = None
    GMP_OD_RELEASING_DECISION: Optional[str] = None
    GMP_OD_RELEASING_REMARKS: Optional[str] = None
    GMP_DATE_OD_RELEASING_END: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "GMP_DATE_DECKER_1_END", "GMP_DATE_EVALUATOR_END",
        "GMP_DATE_CHECKER_END", "GMP_DATE_QA_ADMIN_END",
        "GMP_DATE_LRD_CHIEF_END",
        "GMP_DATE_OD_RECEIVING_END", "GMP_DATE_OD_RELEASING_END",
    )
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


# ─────────────────────────────────────────────────────────────────────────────
# GMPRecord base / create / update / response
# ─────────────────────────────────────────────────────────────────────────────
class GMPRecordBase(BaseModel):
    GMP_DTN: Optional[int] = None
    GMP_RELATED_DTN: Optional[str] = None
    GMP_DATE_RECEIVED: Optional[date] = None
    GMP_LTO_COMPANY: Optional[str] = None
    GMP_LTO_NUMBER: Optional[str] = None
    GMP_LTO_ADDRESS: Optional[str] = None
    GMP_TRANSACTION_TYPE: Optional[str] = None
    GMP_EST_CATEGORY: Optional[str] = None
    GMP_FOREIGN_MANUFACTURER: Optional[str] = None
    GMP_FOREIGN_MANUFACTURER_ADDRESS: Optional[str] = None
    GMP_SECPA_NUMBER: Optional[str] = None
    GMP_CERTIFICATE_NUMBER: Optional[str] = None
    GMP_TYPE_OF_ISSUANCE: Optional[str] = None
    GMP_CERTIFICATE_VALIDITY: Optional[str] = None
    GMP_DECISION: Optional[str] = None
    GMP_APP_STATUS: Optional[str] = None
    GMP_RELEASED_DATE: Optional[date] = None
    GMP_PROCESSED_TIME: Optional[str] = None
    GMP_END_DATE: Optional[date] = None
    GMP_TIMELINE: Optional[str] = None
    GMP_REMARKS: Optional[str] = None
    GMP_NOD_DATE_1: Optional[date] = None
    GMP_NOD_DATE_2: Optional[date] = None
    GMP_NOD_DATE_3: Optional[date] = None
    GMP_NOD_DATE_4: Optional[date] = None
    GMP_NOD_DATE_5: Optional[date] = None
    GMP_DATE_PRINTED: Optional[date] = None
    GMP_COMPLIANCE_DOCS_DATE_RECEIVED: Optional[date] = None
    GMP_PRODUCT_LINE: Optional[str] = None
    GMP_CURRENT_STEP: Optional[str] = None
    GMP_EVALUATOR: Optional[str] = None
    GMP_PICS_NONPICS: Optional[str] = None
    GMP_TRASH: Optional[str] = None
    GMP_REFERENCE_NO: Optional[str] = None
    # Were `Optional[str]` here despite being real timestamp columns on the
    # model (DateTime) — any non-ISO string sent through the create/update API
    # would either fail Pydantic's str validation for weird types, or pass
    # straight through unvalidated into the DB as a raw string. Now proper
    # datetimes with flexible parsing, matching GMPRecordResponse below.
    GMP_TRASH_DATE_ENCODED: Optional[datetime] = None
    GMP_USER_UPLOADER: Optional[str] = None
    GMP_DATE_EXCEL_UPLOAD: Optional[datetime] = None

    @field_validator("GMP_DTN", mode="before")
    @classmethod
    def parse_optional_int(cls, v):
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator(
        "GMP_DATE_RECEIVED", "GMP_RELEASED_DATE", "GMP_END_DATE",
        "GMP_NOD_DATE_1", "GMP_NOD_DATE_2", "GMP_NOD_DATE_3",
        "GMP_NOD_DATE_4", "GMP_NOD_DATE_5",
        "GMP_DATE_PRINTED", "GMP_COMPLIANCE_DOCS_DATE_RECEIVED",
        mode="before",
    )
    @classmethod
    def parse_flexible_dates(cls, v):
        # Accepts any common date format (or an Excel-parsed datetime) and
        # normalizes it to YYYY-MM-DD before it ever reaches the DB layer.
        return _coerce_date(v)

    @field_validator(
        "GMP_TRASH_DATE_ENCODED", "GMP_DATE_EXCEL_UPLOAD",
        mode="before",
    )
    @classmethod
    def parse_flexible_datetimes(cls, v):
        return _coerce_datetime(v)


class GMPRecordCreate(GMPRecordBase):
    pass


class GMPRecordUpdate(GMPRecordBase):
    pass


class GMPIssuanceSummary(BaseModel):
    reference_no: Optional[str] = None
    type_of_issuance: Optional[str] = None
    certificate_number: Optional[str] = None
    certificate_validity: Optional[str] = None
    secpa_number: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class GMPRecordResponse(GMPRecordBase):
    GMP_ID: int
    GMP_DATE_EXCEL_UPLOAD: Optional[datetime] = None
    GMP_TRASH_DATE_ENCODED: Optional[datetime] = None
    gmp_delegation: Optional[GMPDelegationResponse] = None
    # Every sibling reference number under this DTN (added via Add Issuance),
    # each with its own issuance details — only populated for view=main
    # (see get_gmp_records in app/crud/gmp_record.py); empty list otherwise.
    all_issuances: List[GMPIssuanceSummary] = []
    model_config = ConfigDict(from_attributes=True)


class GMPRecordListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[GMPRecordResponse]


class GMPRecordSummary(BaseModel):
    total_records: int
    decked_count: int = 0
    not_decked_count: int = 0
    by_status: dict
    by_category: dict
    recent_uploads: int
    