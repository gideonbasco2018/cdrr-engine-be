# app/schemas/rrdportal.py
from datetime import date, datetime
from typing import List, Optional, Union

from pydantic import BaseModel

# Some tables store these as DATE, some as DATETIME, some as VARCHAR.
DateOrStr = Optional[Union[datetime, date, str]]


# ======================= CMDR =======================

class CmdrProductOut(BaseModel):
    APP_UID: str
    APP_NUMBER: Optional[int] = None
    APP_STATUS: Optional[str] = None
    ROW: int
    PRODUCT_NAME_TEMP: Optional[str] = None
    MANUFACTURER_TEMP: Optional[str] = None
    MDR_DVR_NO_TEMP: Optional[str] = None
    CLASS_TEMP: Optional[str] = None


class CmdrApplicationOut(BaseModel):
    APP_UID: str
    APP_NUMBER: Optional[int] = None
    APP_STATUS: Optional[str] = None
    TYPE_AUTHORIZATION: Optional[str] = None
    TYPE_APPLICATION: Optional[str] = None
    APPLICATION_OPTION: Optional[str] = None
    COMPANY_NAME: Optional[str] = None
    PRODUCT_CAT_TEMP: Optional[str] = None
    DTN: Optional[str] = None
    RE_APPLICATION_DTN: Optional[str] = None
    DATE_RECEIVED_FDAC: DateOrStr = None
    DECKER_REMARKS: Optional[str] = None
    ASSIGNED_DECKER_CODE: Optional[str] = None
    ASSIGNED_DECKER_DISPLAYNAME: Optional[str] = None
    DATE_DECKER_START: DateOrStr = None
    DATE_DECKER_START_HUMAN: Optional[str] = None
    DATE_DECKER_END: DateOrStr = None
    DATE_DECKER_END_HUMAN: Optional[str] = None
    ASSIGN_DECKER_NO_DAYS: Optional[str] = None
    ASSIGN_DECKER_NO_DAYS_STATUS: Optional[str] = None
    ASSIGNED_EVALUATOR_CODE: Optional[str] = None
    ASSIGNED_EVALUATOR_DISPLAYNAME: Optional[str] = None
    EVALUATOR_FINAL_RECOMMENDATION: Optional[str] = None
    EVALUATOR_FINAL_REMARKS: Optional[str] = None
    DATE_EVAL_START: DateOrStr = None
    DATE_EVAL_START_HUMAN: Optional[str] = None
    DATE_EVAL_END: DateOrStr = None
    DATE_EVAL_END_HUMAN: Optional[str] = None
    ASSIGN_EVAL_NO_DAYS: Optional[str] = None
    ASSIGN_EVAL_NO_DAYS_STATUS: Optional[str] = None
    ASSIGNED_CHECKER_CODE: Optional[str] = None
    ASSIGNED_CHECKER_DISPLAYNAME: Optional[str] = None
    CHECKER_RECOM: Optional[str] = None
    CHECKER_REMARKS: Optional[str] = None
    DATE_CHECK_START: Optional[str] = None
    DATE_CHECK_START_HUMAN: Optional[str] = None
    DATE_CHECK_END: Optional[str] = None
    DATE_CHECK_END_HUMAN: Optional[str] = None
    ASSIGN_CHECKER_NO_DAYS: Optional[str] = None
    ASSIGN_CHECKER_NO_DAYS_STATUS: Optional[str] = None
    ASSIGNED_DIRECTOR_CODE: Optional[str] = None
    ASSIGNED_DIRECTOR_DISPLAYNAME: Optional[str] = None
    DATE_DIRECTOR_START: Optional[str] = None
    DATE_DIRECTOR_START_HUMAN: Optional[str] = None
    DATE_DIRECTOR_END: Optional[str] = None
    DATE_DIRECTOR_END_HUMAN: Optional[str] = None
    ASSIGN_DOC_SIGN_NO_DAYS: Optional[str] = None
    ASSIGN_DOC_SIGN_NO_DAYS_STATUS: Optional[str] = None
    ASSIGNED_DOC_RELEASING_DISPLAYNAME: Optional[str] = None
    ASSIGNED_DOC_RELEASING_CODE: Optional[str] = None
    DATE_DOC_RELEASING_START: Optional[str] = None
    DATE_DOC_RELEASING_START_HUMAN: Optional[str] = None
    DATE_DOC_RELEASING_END: Optional[str] = None
    DATE_DOC_RELEASING_END_HUMAN: Optional[str] = None
    ASSIGN_DOC_RELEASING_NO_DAYS: Optional[str] = None
    ASSIGN_DOC_RELEASING_NO_DAYS_STATUS: Optional[str] = None
    TOTAL_NO_DAYS: Optional[str] = None
    COMPANY_ADDRESS: Optional[str] = None  # only exists in PMT_CMDR_INITIAL; null elsewhere


class CmdrDelegationOut(BaseModel):
    """One row of APP_DELEGATION (many per application). DEL_DATA is intentionally left out."""

    APP_UID: str
    DEL_INDEX: int
    DELEGATION_ID: Optional[int] = None
    APP_NUMBER: Optional[int] = None
    DEL_PREVIOUS: Optional[int] = None
    DEL_LAST_INDEX: Optional[int] = None
    PRO_UID: Optional[str] = None
    TAS_UID: Optional[str] = None
    USR_UID: Optional[str] = None
    DEL_TYPE: Optional[str] = None
    DEL_THREAD: Optional[int] = None
    DEL_THREAD_STATUS: Optional[str] = None
    DEL_PRIORITY: Optional[str] = None
    DEL_DELEGATE_DATE: DateOrStr = None
    DEL_INIT_DATE: DateOrStr = None
    DEL_FINISH_DATE: DateOrStr = None
    DEL_TASK_DUE_DATE: DateOrStr = None
    DEL_RISK_DATE: DateOrStr = None
    DEL_DURATION: Optional[float] = None
    DEL_QUEUE_DURATION: Optional[float] = None
    DEL_DELAY_DURATION: Optional[float] = None
    DEL_STARTED: Optional[int] = None
    DEL_FINISHED: Optional[int] = None
    DEL_DELAYED: Optional[int] = None
    APP_OVERDUE_PERCENTAGE: Optional[float] = None
    USR_ID: Optional[int] = None
    PRO_ID: Optional[int] = None
    TAS_ID: Optional[int] = None


class CmdrApplicationDetail(CmdrApplicationOut):
    products: List[CmdrProductOut] = []
    delegations: List[CmdrDelegationOut] = []


class CmdrListItem(CmdrApplicationOut):
    # null unless requested with include_products / include_delegations
    products: Optional[List[CmdrProductOut]] = None
    delegations: Optional[List[CmdrDelegationOut]] = None


class CmdrApplicationPage(BaseModel):
    items: List[CmdrListItem]
    total: int
    skip: int
    limit: int


class CmdrAllItem(CmdrListItem):
    CMDR_TYPE: str  # which table the row came from: initial / initial_abridge / renewal / amendment


class CmdrAllPage(BaseModel):
    items: List[CmdrAllItem]
    total: int
    skip: int
    limit: int


class CmdrFilterOptions(BaseModel):
    cmdr_types: List[str]
    type_application: List[str]
    application_option: List[str]
    app_status: List[str]


class FacetItem(BaseModel):
    value: str
    count: int


class CmdrFacets(BaseModel):
    """Counts per value for each filter. Each facet ignores its own filter, so the
    counts show what you would get by switching to that value."""

    cmdr_type: List[FacetItem]
    type_application: List[FacetItem]
    application_option: List[FacetItem]
    app_status: List[FacetItem]