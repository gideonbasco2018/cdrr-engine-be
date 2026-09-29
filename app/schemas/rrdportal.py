# app/schemas/rrdportal.py
from datetime import date
from typing import List, Optional

from pydantic import BaseModel

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


class CmdrInitialOut(BaseModel):
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
    DATE_RECEIVED_FDAC: Optional[date] = None
    DECKER_REMARKS: Optional[str] = None
    ASSIGNED_DECKER_CODE: Optional[str] = None
    ASSIGNED_DECKER_DISPLAYNAME: Optional[str] = None
    DATE_DECKER_START: Optional[date] = None
    DATE_DECKER_START_HUMAN: Optional[str] = None
    DATE_DECKER_END: Optional[date] = None
    DATE_DECKER_END_HUMAN: Optional[str] = None
    ASSIGN_DECKER_NO_DAYS: Optional[str] = None
    ASSIGN_DECKER_NO_DAYS_STATUS: Optional[str] = None
    ASSIGNED_EVALUATOR_CODE: Optional[str] = None
    ASSIGNED_EVALUATOR_DISPLAYNAME: Optional[str] = None
    EVALUATOR_FINAL_RECOMMENDATION: Optional[str] = None
    EVALUATOR_FINAL_REMARKS: Optional[str] = None
    DATE_EVAL_START: Optional[date] = None
    DATE_EVAL_START_HUMAN: Optional[str] = None
    DATE_EVAL_END: Optional[date] = None
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
    COMPANY_ADDRESS: Optional[str] = None


class CmdrInitialDetail(CmdrInitialOut):
    products: List[CmdrProductOut] = []


class CmdrInitialPage(BaseModel):
    items: List[CmdrInitialOut]
    total: int
    skip: int
    limit: int
