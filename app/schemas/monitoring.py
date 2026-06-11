from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List


class TaskStatusBreakdown(BaseModel):
    completed: int
    in_progress: int
    total: int


class UserTaskSummary(BaseModel):
    user_id: int
    username: str
    full_name: str
    position: Optional[str] = None
    group_name: Optional[str] = None
    role: str
    is_active: bool
    tasks: TaskStatusBreakdown

    class Config:
        orm_mode = True


class UsersTasksResponse(BaseModel):
    total_users: int
    data: List[UserTaskSummary]


class RecordItem(BaseModel):
    id: int
    dtn: Optional[str] = None
    user_name: Optional[str] = None
    drug_name: Optional[str] = None
    date_received_cent: Optional[str] = None
    timeline: Optional[str] = None
    app_step: Optional[str] = None
    app_status: Optional[str] = None
    prescription: Optional[str] = None

    class Config:
        orm_mode = True


class AllRecordsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[RecordItem]

# -----------------------------
# Release record response
# -----------------------------
class ReleaseRecord(BaseModel):
    DB_ID: int
    DB_DTN: Optional[int] = None
    DB_PROD_BR_NAME: Optional[str] = None
    DB_PROD_GEN_NAME: Optional[str] = None
    DB_SECPA_EXP_DATE: Optional[str] = None
    DB_SECPA_ISSUED_ON: Optional[str] = None
    DB_APP_STATUS: Optional[str] = None
    DB_TYPE_DOC_RELEASED: Optional[str] = None
    DB_DATE_RELEASED: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReleaseListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[ReleaseRecord]

# -----------------------------
# Overview KPI Summary
# -----------------------------
class OverviewSummaryResponse(BaseModel):
    total_applications: int
    cpr_released: int
    on_process: int
    lod_released: int


# ── DTN date range filter schema (used internally / for OpenAPI docs) ──────────
# Both fields are 8-digit strings (YYYYMMDD).  The frontend always sends full
# 8-digit values by padding omitted month/day (From → 01/01, To → 12/31).
class DtnDateRangeFilter(BaseModel):
    dtn_date_from: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description=(
            "Lower bound for DTN date range.  Must be YYYYMMDD (8 digits). "
            "Filters records where LEFT(dtn, 8) >= dtn_date_from."
        ),
        example="20230101",
    )
    dtn_date_to: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description=(
            "Upper bound for DTN date range.  Must be YYYYMMDD (8 digits). "
            "Filters records where LEFT(dtn, 8) <= dtn_date_to."
        ),
        example="20261231",
    )


# ── CPR Trend (Received & Released) ───────────────────────────────────────────
class CprTrendItem(BaseModel):
    period: str  # e.g. "2025-01", "2025-02"
    received_count: int = 0
    released_count: int = 0


class CprTrendResponse(BaseModel):
    data: List[CprTrendItem]
    countries: List[str]  # unique country values for the chosen country_type
    doc_types: List[str]  # unique DB_TYPE_DOC_RELEASED values for dropdown


# ── Processing Trend ───────────────────────────────────────────────────────────
 
class ProcessingTrendItem(BaseModel):
    """One data point in the trend series — one period (month or year)."""
    period: str                  # e.g. "2025-01" (monthly) or "2025" (yearly)
    received_count: int = 0      # records where DB_DATE_RECEIVED_CENT falls in period
    released_count: int = 0      # records where DB_DATE_RELEASED falls in period
 
 
class ProcessingTrendResponse(BaseModel):
    data: List[ProcessingTrendItem]
 
    # Dropdown option lists returned alongside the data so the frontend
    # can populate its filter controls in a single request.
    doc_types: List[str]         # distinct DB_TYPE_DOC_RELEASED values
    processing_types: List[str]  # distinct DB_PROCESSING_TYPE values
    entry_types: List[str]       # distinct DB_ENTRY_TYPE values
    app_statuses: List[str]      # distinct DB_APP_STATUS values
    app_types: List[str]         # distinct DB_APP_TYPE values
 
 
class ProcessingStatsSummary(BaseModel):
    """Aggregate counts broken down by a categorical column."""
    label: str     # e.g. "CPR", "ORIGINAL", "APPROVED"
    count: int
 
 
class ProcessingBreakdownResponse(BaseModel):
    """
    Breakdown of record counts by one dimension (doc_type, processing_type,
    entry_type, app_status, or app_type) for the filtered result set.
    Used to power pie / bar charts.
    """
    dimension: str                      # which column was grouped
    data: List[ProcessingStatsSummary]
 
    # Same dropdown lists as ProcessingTrendResponse
    doc_types: List[str]
    processing_types: List[str]
    entry_types: List[str]
    app_statuses: List[str]
    app_types: List[str]

# ── Summary (formerly Weekly Status) ──────────────────────────────────────────

class SummaryRow(BaseModel):
    app_type: str
    carry_over: int = 0
    received: int = 0
    processed: int = 0
    total_pending: int = 0


class SummaryStatusRow(BaseModel):
    label: str
    count: int
    highlight: bool = False
    right_align: bool = False


class SummaryResponse(BaseModel):
    period_label: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    rows: List[SummaryRow]
    overall_status: List[SummaryStatusRow]