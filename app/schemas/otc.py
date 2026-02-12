from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class OTCUploadResponse(BaseModel):
    success: bool
    message: str
    stats: Dict[str, int]
    errors: List[Dict[str, Any]] = []


class OTCRecordUpdate(BaseModel):
    """Schema for updating OTC records - all fields are optional"""
    DB_DTN: Optional[str] = None
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
    DB_DATE_ISSUED: Optional[date] = None
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
    DB_PHARMA_PROD_CAT: Optional[str] = None
    DB_PHARMA_PROD_CAT_LABEL: Optional[str] = None
    DB_IS_IN_PM: Optional[int] = None
    DB_TIMELINE_CITIZEN_CHARTER: Optional[int] = None

    class Config:
        from_attributes = True