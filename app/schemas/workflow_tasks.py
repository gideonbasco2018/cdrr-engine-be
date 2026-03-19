"""
Schemas for ApplicationLogs + MainDB Joined View
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# ---------------------
# Full MainDB Info (all columns)
# ---------------------
class MainDBBrief(BaseModel):
    """All MainDB columns embedded in joined log response"""
    DB_ID: int

    # Establishment Information
    DB_DTN: Optional[int] = None
    DB_EST_CAT: Optional[str] = None
    DB_EST_LTO_COMP: Optional[str] = None
    DB_EST_LTO_ADD: Optional[str] = None
    DB_EST_EADD: Optional[str] = None
    DB_EST_TIN: Optional[str] = None
    DB_EST_CONTACT_NO: Optional[str] = None
    DB_EST_LTO_NO: Optional[str] = None
    DB_EST_VALIDITY: Optional[str] = None

    # Product Information
    DB_PROD_BR_NAME: Optional[str] = None
    DB_PROD_GEN_NAME: Optional[str] = None
    DB_PROD_DOS_STR: Optional[str] = None
    DB_PROD_DOS_FORM: Optional[str] = None
    DB_PROD_CLASS_PRESCRIP: Optional[str] = None
    DB_PROD_ESS_DRUG_LIST: Optional[str] = None
    DB_PROD_PHARMA_CAT: Optional[str] = None

    # Manufacturer Information
    DB_PROD_MANU: Optional[str] = None
    DB_PROD_MANU_ADD: Optional[str] = None
    DB_PROD_MANU_TIN: Optional[str] = None
    DB_PROD_MANU_LTO_NO: Optional[str] = None
    DB_PROD_MANU_COUNTRY: Optional[str] = None

    # Trader Information
    DB_PROD_TRADER: Optional[str] = None
    DB_PROD_TRADER_ADD: Optional[str] = None
    DB_PROD_TRADER_TIN: Optional[str] = None
    DB_PROD_TRADER_LTO_NO: Optional[str] = None
    DB_PROD_TRADER_COUNTRY: Optional[str] = None

    # Repacker Information
    DB_PROD_REPACKER: Optional[str] = None
    DB_PROD_REPACKER_ADD: Optional[str] = None
    DB_PROD_REPACKER_TIN: Optional[str] = None
    DB_PROD_REPACKER_LTO_NO: Optional[str] = None
    DB_PROD_REPACKER_COUNTRY: Optional[str] = None

    # Importer Information
    DB_PROD_IMPORTER: Optional[str] = None
    DB_PROD_IMPORTER_ADD: Optional[str] = None
    DB_PROD_IMPORTER_TIN: Optional[str] = None
    DB_PROD_IMPORTER_LTO_NO: Optional[str] = None
    DB_PROD_IMPORTER_COUNTRY: Optional[str] = None

    # Distributor Information
    DB_PROD_DISTRI: Optional[str] = None
    DB_PROD_DISTRI_ADD: Optional[str] = None
    DB_PROD_DISTRI_TIN: Optional[str] = None
    DB_PROD_DISTRI_LTO_NO: Optional[str] = None
    DB_PROD_DISTRI_COUNTRY: Optional[str] = None
    DB_PROD_DISTRI_SHELF_LIFE: Optional[str] = None

    # Storage & Packaging
    DB_STORAGE_COND: Optional[str] = None
    DB_PACKAGING: Optional[str] = None
    DB_SUGG_RP: Optional[str] = None

    # Samples & Dates
    DB_NO_SAMPLE: Optional[str] = None
    DB_EXPIRY_DATE: Optional[str] = None
    DB_CPR_VALIDITY: Optional[str] = None

    # Registration & Application
    DB_REG_NO: Optional[str] = None
    DB_APP_TYPE: Optional[str] = None
    DB_MOTHER_APP_TYPE: Optional[str] = None
    DB_OLD_RSN: Optional[str] = None
    DB_AMMEND1: Optional[str] = None
    DB_AMMEND2: Optional[str] = None
    DB_AMMEND3: Optional[str] = None

    # Category & Certification
    DB_PROD_CAT: Optional[str] = None
    DB_CERTIFICATION: Optional[str] = None

    # Financial Information
    DB_FEE: Optional[str] = None
    DB_LRF: Optional[str] = None
    DB_SURC: Optional[str] = None
    DB_TOTAL: Optional[str] = None
    DB_OR_NO: Optional[str] = None
    DB_DATE_ISSUED: Optional[str] = None

    # Receiving Dates
    DB_DATE_RECEIVED_FDAC: Optional[str] = None
    DB_DATE_RECEIVED_CENT: Optional[str] = None
    DB_MO: Optional[str] = None

    # Document Information
    DB_FILE: Optional[str] = None

    # SECPA Information
    DB_SECPA: Optional[str] = None
    DB_SECPA_EXP_DATE: Optional[str] = None
    DB_SECPA_ISSUED_ON: Optional[str] = None

    # Evaluation & Decking
    DB_DECKING_SCHED: Optional[str] = None
    DB_EVAL: Optional[str] = None
    DB_DATE_DECK: Optional[str] = None

    # Remarks
    DB_REMARKS_1: Optional[str] = None
    DB_DATE_REMARKS: Optional[str] = None

    # Classification & Release
    DB_CLASS: Optional[str] = None
    DB_DATE_RELEASED: Optional[str] = None
    DB_TYPE_DOC_RELEASED: Optional[str] = None
    DB_ATTA_RELEASED: Optional[str] = None

    # CPR Conditions
    DB_CPR_COND: Optional[str] = None
    DB_CPR_COND_REMARKS: Optional[str] = None
    DB_CPR_COND_ADD_REMARKS: Optional[str] = None

    # Status & Tracking
    DB_APP_STATUS: Optional[str] = None
    DB_APP_REMARKS: Optional[str] = None
    DB_TRASH: Optional[str] = None
    DB_TRASH_DATE_ENCODED: Optional[datetime] = None
    DB_USER_UPLOADER: Optional[str] = None
    DB_DATE_EXCEL_UPLOAD: Optional[datetime] = None

    # Pharmaceutical Product Category
    DB_PHARMA_PROD_CAT: Optional[str] = None
    DB_PHARMA_PROD_CAT_LABEL: Optional[str] = None
    DB_IS_IN_PM: Optional[int] = None

    DB_TIMELINE_CITIZEN_CHARTER: Optional[int] = None

    # Processing Type
    DB_PROCESSING_TYPE: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------
# Single Log Row joined with MainDB
# ---------------------
class LogWithMainDBResponse(BaseModel):
    """
    Single ApplicationLog row joined with MainDB.
    Used for table rows.
    """
    # Log fields
    id: int
    main_db_id: int
    application_step: Optional[str] = None
    user_name: Optional[str] = None
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    start_date: Optional[datetime] = None
    accomplished_date: Optional[datetime] = None
    del_index: Optional[int] = None
    del_previous: Optional[int] = None
    del_last_index: Optional[int] = None
    del_thread: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Compliance deadline fields
    deadline_date: Optional[date] = None
    working_days: Optional[int] = None

    # ── Read tracking ──
    is_read: int = 0
    read_at: Optional[datetime] = None

    # ── Received tracking ──
    is_received: int = 0
    received_at: Optional[datetime] = None
    received_by: Optional[str] = None

    # Joined MainDB info
    main_db: Optional[MainDBBrief] = None

    class Config:
        from_attributes = True


# ---------------------
# Mark as Read response
# ---------------------
class MarkReadResponse(BaseModel):
    id: int
    is_read: int
    read_at: Optional[datetime] = None


# ---------------------
# Mark as Received — request + response
# ---------------------
class MarkReceivedRequest(BaseModel):
    """Bulk mark-as-received request body."""
    ids: List[int] = Field(..., min_length=1, description="List of log IDs to mark as received")


class MarkReceivedItemResponse(BaseModel):
    """Single item result in a bulk mark-as-received response."""
    id: int
    is_received: int
    received_at: Optional[datetime] = None
    received_by: Optional[str] = None


class MarkReceivedBulkResponse(BaseModel):
    """Response for bulk mark-as-received."""
    updated: int                              # how many rows were actually changed
    skipped: int                              # already received — no-op
    results: List[MarkReceivedItemResponse]


# ---------------------
# Paginated List Response
# ---------------------
class LogWithMainDBListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[LogWithMainDBResponse]