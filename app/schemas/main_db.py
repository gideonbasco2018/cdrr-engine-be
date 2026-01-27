# app/schemas/main_db.py

from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional, List
from datetime import datetime


# -----------------------------
# ApplicationLogs schema
# -----------------------------
class ApplicationLogResponse(BaseModel):
    id: int
    main_db_id: int
    application_step: Optional[str] = None
    user_name: Optional[str] = None
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    start_date: Optional[datetime] = None
    accomplished_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# ApplicationDelegation schema
# -----------------------------
class ApplicationDelegationResponse(BaseModel):
    DB_DECKER: Optional[str] = None
    DB_DECKER_DECISION: Optional[str] = None
    DB_DECKER_REMARKS: Optional[str] = None
    DB_DATE_DECKED_END: Optional[datetime] = None
    
    DB_EVALUATOR: Optional[str] = None
    DB_EVAL_DECISION: Optional[str] = None
    DB_EVAL_REMARKS: Optional[str] = None
    DB_DATE_EVAL_END: Optional[datetime] = None
    
    DB_CHECKER: Optional[str] = None
    DB_CHECKER_DECISION: Optional[str] = None
    DB_CHECKER_REMARKS: Optional[str] = None
    DB_DATE_CHECKER_END: Optional[datetime] = None
    
    DB_SUPERVISOR: Optional[str] = None
    DB_SUPERVISOR_DECISION: Optional[str] = None
    DB_SUPERVISOR_REMARKS: Optional[str] = None
    DB_DATE_SUPERVISOR_END: Optional[datetime] = None
    
    DB_QA: Optional[str] = None
    DB_QA_DECISION: Optional[str] = None
    DB_QA_REMARKS: Optional[str] = None
    DB_DATE_QA_END: Optional[datetime] = None
    
    DB_DIRECTOR: Optional[str] = None
    DB_DIRECTOR_DECISION: Optional[str] = None
    DB_DIRECTOR_REMARKS: Optional[str] = None
    DB_DATE_DIRECTOR_END: Optional[datetime] = None

    DB_RELEASING_OFFICER: Optional[str] = None
    DB_RELEASING_OFFICER_DECISION: Optional[str] = None
    DB_RELEASING_OFFICER_REMARKS: Optional[str] = None
    DB_RELEASING_OFFICER_END: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer(
        'DB_DATE_DECKED_END', 
        'DB_DATE_EVAL_END',
        'DB_DATE_CHECKER_END',
        'DB_DATE_SUPERVISOR_END',
        'DB_DATE_QA_END',
        'DB_DATE_DIRECTOR_END',
        'DB_RELEASING_OFFICER_END'
    )
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


# -----------------------------
# MainDB base schema (create/update)
# -----------------------------
class MainDBBase(BaseModel):
    """Base schema with all fields as optional"""

    DB_DTN: Optional[int] = None
    DB_EST_CAT: Optional[str] = None
    DB_EST_LTO_COMP: Optional[str] = None
    DB_EST_LTO_ADD: Optional[str] = None
    DB_EST_EADD: Optional[str] = None
    DB_EST_TIN: Optional[str] = None
    DB_EST_CONTACT_NO: Optional[str] = None
    DB_EST_LTO_NO: Optional[str] = None
    DB_EST_VALIDITY: Optional[str] = None

    DB_PROD_BR_NAME: Optional[str] = None
    DB_PROD_GEN_NAME: Optional[str] = None
    DB_PROD_DOS_STR: Optional[str] = None
    DB_PROD_DOS_FORM: Optional[str] = None
    DB_PROD_CLASS_PRESCRIP: Optional[str] = None
    DB_PROD_ESS_DRUG_LIST: Optional[str] = None
    DB_PROD_PHARMA_CAT: Optional[str] = None

    DB_PROD_MANU: Optional[str] = None
    DB_PROD_MANU_ADD: Optional[str] = None
    DB_PROD_MANU_TIN: Optional[str] = None
    DB_PROD_MANU_LTO_NO: Optional[str] = None
    DB_PROD_MANU_COUNTRY: Optional[str] = None

    DB_PROD_TRADER: Optional[str] = None
    DB_PROD_TRADER_ADD: Optional[str] = None
    DB_PROD_TRADER_TIN: Optional[str] = None
    DB_PROD_TRADER_LTO_NO: Optional[str] = None
    DB_PROD_TRADER_COUNTRY: Optional[str] = None

    DB_PROD_REPACKER: Optional[str] = None
    DB_PROD_REPACKER_ADD: Optional[str] = None
    DB_PROD_REPACKER_TIN: Optional[str] = None
    DB_PROD_REPACKER_LTO_NO: Optional[str] = None
    DB_PROD_REPACKER_COUNTRY: Optional[str] = None

    DB_PROD_IMPORTER: Optional[str] = None
    DB_PROD_IMPORTER_ADD: Optional[str] = None
    DB_PROD_IMPORTER_TIN: Optional[str] = None
    DB_PROD_IMPORTER_LTO_NO: Optional[str] = None
    DB_PROD_IMPORTER_COUNTRY: Optional[str] = None

    DB_PROD_DISTRI: Optional[str] = None
    DB_PROD_DISTRI_ADD: Optional[str] = None
    DB_PROD_DISTRI_TIN: Optional[str] = None
    DB_PROD_DISTRI_LTO_NO: Optional[str] = None
    DB_PROD_DISTRI_COUNTRY: Optional[str] = None
    DB_PROD_DISTRI_SHELF_LIFE: Optional[str] = None

    DB_STORAGE_COND: Optional[str] = None
    DB_PACKAGING: Optional[str] = None
    DB_SUGG_RP: Optional[str] = None

    DB_NO_SAMPLE: Optional[str] = None
    DB_EXPIRY_DATE: Optional[str] = None
    DB_CPR_VALIDITY: Optional[str] = None

    DB_REG_NO: Optional[str] = None
    DB_APP_TYPE: Optional[str] = None
    DB_MOTHER_APP_TYPE: Optional[str] = None
    DB_OLD_RSN: Optional[str] = None
    DB_AMMEND1: Optional[str] = None
    DB_AMMEND2: Optional[str] = None
    DB_AMMEND3: Optional[str] = None

    DB_PROD_CAT: Optional[str] = None
    DB_CERTIFICATION: Optional[str] = None

    DB_FEE: Optional[str] = None
    DB_LRF: Optional[str] = None
    DB_SURC: Optional[str] = None
    DB_TOTAL: Optional[str] = None
    DB_OR_NO: Optional[str] = None
    DB_DATE_ISSUED: Optional[str] = None

    DB_DATE_RECEIVED_FDAC: Optional[str] = None
    DB_DATE_RECEIVED_CENT: Optional[str] = None
    DB_MO: Optional[str] = None

    DB_FILE: Optional[str] = None

    DB_SECPA: Optional[str] = None
    DB_SECPA_EXP_DATE: Optional[str] = None
    DB_SECPA_ISSUED_ON: Optional[str] = None

    DB_DECKING_SCHED: Optional[str] = None
    DB_EVAL: Optional[str] = None
    DB_DATE_DECK: Optional[str] = None

    DB_REMARKS_1: Optional[str] = None
    DB_DATE_REMARKS: Optional[str] = None

    DB_CLASS: Optional[str] = None
    DB_DATE_RELEASED: Optional[str] = None
    DB_TYPE_DOC_RELEASED: Optional[str] = None
    DB_ATTA_RELEASED: Optional[str] = None

    DB_CPR_COND: Optional[str] = None
    DB_CPR_COND_REMARKS: Optional[str] = None
    DB_CPR_COND_ADD_REMARKS: Optional[str] = None

    DB_APP_STATUS: Optional[str] = None
    DB_APP_REMARKS: Optional[str] = None
    DB_TRASH: Optional[str] = None
    DB_TRASH_DATE_ENCODED: Optional[str] = None
    DB_USER_UPLOADER: Optional[str] = None
    DB_DATE_EXCEL_UPLOAD: Optional[str] = None

    DB_PHARMA_PROD_CAT: Optional[str] = None
    DB_PHARMA_PROD_CAT_LABEL: Optional[str] = None
    DB_IS_IN_PM: Optional[int] = None
    DB_TIMELINE_CITIZEN_CHARTER: Optional[int] = None  # ✅ NEW


class MainDBCreate(MainDBBase):
    pass


class MainDBUpdate(MainDBBase):
    pass


# -----------------------------
# MainDB response schema (with delegation)
# -----------------------------
class MainDBResponse(MainDBBase):
    DB_ID: int
    DB_DATE_EXCEL_UPLOAD: Optional[datetime] = None
    DB_TRASH_DATE_ENCODED: Optional[datetime] = None

    application_delegation: Optional[ApplicationDelegationResponse] = None

    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# Paginated list response
# -----------------------------
class MainDBListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[MainDBResponse]


# -----------------------------
# Optional summary schema
# -----------------------------
class MainDBSummary(BaseModel):
    total_records: int
    decked_count: int = 0
    not_decked_count: int = 0
    by_status: dict
    by_category: dict
    recent_uploads: int