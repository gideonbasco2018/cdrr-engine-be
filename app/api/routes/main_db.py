from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_  # ✅ FIXED - Added or_ import
from typing import Optional, List
import pandas as pd
import io
from datetime import datetime
import math
import numpy as np
from dateutil import parser

from app.db.session import get_db
from app.schemas.main_db import (
    MainDBCreate, 
    MainDBUpdate, 
    MainDBResponse, 
    MainDBListResponse, 
    MainDBSummary, 
    ApplicationLogResponse
)
from app.crud import main_db as crud
from app.crud.main_db import get_main_db_records, get_application_logs
from app.models.main_db import MainDB  # ✅ FIXED - Added MainDB import
from app.models.application_delegation import ApplicationDelegation
from app.core.deps import get_current_active_user  

router = APIRouter(
    prefix="/api/main-db",
    tags=["Main Database"],
    dependencies=[Depends(get_current_active_user)] 
)

# ---------------------
# Constants
# ---------------------
COLUMN_MAPPING = {
    "DTN": "DB_DTN",
    "Est. Category": "DB_EST_CAT",
    "LTO Company": "DB_EST_LTO_COMP",
    "LTO Address": "DB_EST_LTO_ADD",
    "Email": "DB_EST_EADD",
    "TIN": "DB_EST_TIN",
    "Contact No.": "DB_EST_CONTACT_NO",
    "LTO No.": "DB_EST_LTO_NO",
    "Validity": "DB_EST_VALIDITY",
    "Brand Name": "DB_PROD_BR_NAME",
    "Generic Name": "DB_PROD_GEN_NAME",
    "Dosage Strength": "DB_PROD_DOS_STR",
    "Dosage Form": "DB_PROD_DOS_FORM",
    "Prescription": "DB_PROD_CLASS_PRESCRIP",
    "Essential Drug": "DB_PROD_ESS_DRUG_LIST",
    "Pharma Category": "DB_PROD_PHARMA_CAT",
    "Manufacturer": "DB_PROD_MANU",
    "Manufacturer Address": "DB_PROD_MANU_ADD",
    "Manufacturer TIN": "DB_PROD_MANU_TIN",
    "Manufacturer LTO No.": "DB_PROD_MANU_LTO_NO",
    "Manufacturer Country": "DB_PROD_MANU_COUNTRY",
    "Trader": "DB_PROD_TRADER",
    "Trader Address": "DB_PROD_TRADER_ADD",
    "Trader TIN": "DB_PROD_TRADER_TIN",
    "Trader LTO No.": "DB_PROD_TRADER_LTO_NO",
    "Trader Country": "DB_PROD_TRADER_COUNTRY",
    "Repacker": "DB_PROD_REPACKER",
    "Repacker Address": "DB_PROD_REPACKER_ADD",
    "Repacker TIN": "DB_PROD_REPACKER_TIN",
    "Repacker LTO No.": "DB_PROD_REPACKER_LTO_NO",
    "Repacker Country": "DB_PROD_REPACKER_COUNTRY",
    "Importer": "DB_PROD_IMPORTER",
    "Importer Address": "DB_PROD_IMPORTER_ADD",
    "Importer TIN": "DB_PROD_IMPORTER_TIN",
    "Importer LTO No.": "DB_PROD_IMPORTER_LTO_NO",
    "Importer Country": "DB_PROD_IMPORTER_COUNTRY",
    "Distributor": "DB_PROD_DISTRI",
    "Distributor Address": "DB_PROD_DISTRI_ADD",
    "Distributor TIN": "DB_PROD_DISTRI_TIN",
    "Distributor LTO No.": "DB_PROD_DISTRI_LTO_NO",
    "Distributor Country": "DB_PROD_DISTRI_COUNTRY",
    "Shelf Life": "DB_PROD_DISTRI_SHELF_LIFE",
    "Storage Condition": "DB_STORAGE_COND",
    "Packaging": "DB_PACKAGING",
    "Suggested RP": "DB_SUGG_RP",
    "No. Sample": "DB_NO_SAMPLE",
    "Expiry Date": "DB_EXPIRY_DATE",
    "CPR Validity": "DB_CPR_VALIDITY",
    "Registration No.": "DB_REG_NO",
    "App Type": "DB_APP_TYPE",
    "Mother App Type": "DB_MOTHER_APP_TYPE",
    "Old RSN": "DB_OLD_RSN",
    "Amendment 1": "DB_AMMEND1",
    "Amendment 2": "DB_AMMEND2",
    "Amendment 3": "DB_AMMEND3",
    "Product Category": "DB_PROD_CAT",
    "Certification": "DB_CERTIFICATION",
    "Fee": "DB_FEE",
    "LRF": "DB_LRF",
    "SURC": "DB_SURC",
    "Total": "DB_TOTAL",
    "OR No.": "DB_OR_NO",
    "Date Issued": "DB_DATE_ISSUED",
    "Date Received FDAC": "DB_DATE_RECEIVED_FDAC",
    "Date Received Central": "DB_DATE_RECEIVED_CENT",
    "MO": "DB_MO",
    "File": "DB_FILE",
    "SECPA": "DB_SECPA",
    "SECPA Exp Date": "DB_SECPA_EXP_DATE",
    "SECPA Issued On": "DB_SECPA_ISSUED_ON",
    "Decking Schedule": "DB_DECKING_SCHED",
    "Evaluation": "DB_EVAL",
    "Date Deck": "DB_DATE_DECK",
    "Remarks 1": "DB_REMARKS_1",
    "Date Remarks": "DB_DATE_REMARKS",
    "Class": "DB_CLASS",
    "Date Released": "DB_DATE_RELEASED",
    "Type Doc Released": "DB_TYPE_DOC_RELEASED",
    "Atta Released": "DB_ATTA_RELEASED",
    "CPR Condition": "DB_CPR_COND",
    "CPR Cond Remarks": "DB_CPR_COND_REMARKS",
    "CPR Cond Add Remarks": "DB_CPR_COND_ADD_REMARKS",
    "App Status": "DB_APP_STATUS",
    "Trash": "DB_TRASH",
    "Pharma Prod Cat": "DB_PHARMA_PROD_CAT",
    "Pharma Prod Cat Label": "DB_PHARMA_PROD_CAT_LABEL",
    "Is in PM": "DB_IS_IN_PM",
    "Timeline Citizen Charter": "DB_TIMELINE_CITIZEN_CHARTER"
}

# Application Delegation Column Mapping
DELEGATION_COLUMN_MAPPING = {
    "Decker": "DB_DECKER",
    "Decker Decision": "DB_DECKER_DECISION",
    "Decker Remarks": "DB_DECKER_REMARKS",
    "Date Decked End": "DB_DATE_DECKED_END",
    "Evaluator": "DB_EVALUATOR",
    "Evaluator Decision": "DB_EVAL_DECISION",
    "Evaluator Remarks": "DB_EVAL_REMARKS",
    "Date Eval End": "DB_DATE_EVAL_END",
    "Checker": "DB_CHECKER",
    "Checker Decision": "DB_CHECKER_DECISION",
    "Checker Remarks": "DB_CHECKER_REMARKS",
    "Date Checker End": "DB_DATE_CHECKER_END",
    "Supervisor": "DB_SUPERVISOR",
    "Supervisor Decision": "DB_SUPERVISOR_DECISION",
    "Supervisor Remarks": "DB_SUPERVISOR_REMARKS",
    "Date Supervisor End": "DB_DATE_SUPERVISOR_END",
    "QA": "DB_QA",
    "QA Decision": "DB_QA_DECISION",
    "QA Remarks": "DB_QA_REMARKS",
    "Date QA End": "DB_DATE_QA_END",
    "Director": "DB_DIRECTOR",
    "Director Decision": "DB_DIRECTOR_DECISION",
    "Director Remarks": "DB_DIRECTOR_REMARKS",
    "Date Director End": "DB_DATE_DIRECTOR_END",
    "Releasing Officer": "DB_RELEASING_OFFICER",
    "Releasing Officer Decision": "DB_RELEASING_OFFICER_DECISION",
    "Releasing Officer Remarks": "DB_RELEASING_OFFICER_REMARKS",
    "Date Releasing Officer End": "DB_RELEASING_OFFICER_END"
}

# Date and numeric field definitions
DATE_FIELDS = {
    'DB_EST_VALIDITY', 'DB_EXPIRY_DATE', 'DB_CPR_VALIDITY', 
    'DB_DATE_ISSUED', 'DB_DATE_DECK', 'DB_DATE_RECEIVED_FDAC',
    'DB_DATE_RECEIVED_CENT', 'DB_SECPA_EXP_DATE', 'DB_SECPA_ISSUED_ON',
    'DB_DATE_REMARKS', 'DB_DATE_RELEASED'
}

DELEGATION_DATE_FIELDS = {
    'DB_DATE_DECKED_END', 'DB_DATE_EVAL_END', 'DB_DATE_CHECKER_END',
    'DB_DATE_SUPERVISOR_END', 'DB_DATE_QA_END', 'DB_DATE_DIRECTOR_END',
    'DB_RELEASING_OFFICER_END'
}

NUMERIC_STRING_FIELDS = {'DB_FEE', 'DB_LRF', 'DB_SURC', 'DB_TOTAL'}

# ✅ Integer fields that should be stored as integers, not strings
INTEGER_FIELDS = {'DB_DTN', 'DB_IS_IN_PM', 'DB_TIMELINE_CITIZEN_CHARTER'}


# ---------------------
# Helper Functions
# ---------------------
def parse_date_value(value):
    """Parse various date formats and return datetime object or None"""
    if pd.isna(value) or value is None or value == '':
        return None
    
    # If already a datetime/Timestamp, return it
    if isinstance(value, (datetime, pd.Timestamp)):
        return value
    
    # If numeric (Excel serial date or invalid), return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        return None
    
    # Try to parse string dates
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        
        try:
            # Use dateutil parser which handles many formats
            parsed_date = parser.parse(value, fuzzy=True)
            return parsed_date
        except:
            return None
    
    return None


# ---------------------
# Routes
# ---------------------

@router.get("/", response_model=MainDBListResponse)
def get_main_db(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=1000),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    # ✅ NEW FILTERS - All optional and reusable
    prescription: Optional[str] = Query(None, description="Filter by Prescription (e.g., 'OTC', 'Rx')"),
    prescription_not: Optional[str] = Query(None, description="Exclude by Prescription (e.g., NOT 'Over-the-Counter (OTC) Drug')"),
    dtn: Optional[int] = Query(None, description="Filter by DTN (Document Tracking Number)"),
    manufacturer: Optional[str] = Query(None, description="Filter by Manufacturer"),
    lto_company: Optional[str] = Query(None, description="Filter by LTO Company"),
    brand_name: Optional[str] = Query(None, description="Filter by Brand Name"),
    generic_name: Optional[str] = Query(None, description="Filter by Generic Name"),
    app_status: Optional[str] = Query(None, description="Filter by Application Status"),
    app_type: Optional[str] = Query(None, description="Filter by Application Type (DB_APP_TYPE). Use empty string for records without app type."),
    # END NEW FILTERS
    sort_by: str = Query("DB_DATE_EXCEL_UPLOAD"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get paginated list of main database records with flexible filtering"""
    skip = (page - 1) * page_size
    
    # Build filters dictionary
    filters = {
        "status": status,
        "category": category,
        "prescription": prescription,
        "prescription_not": prescription_not,
        "dtn": dtn,
        "manufacturer": manufacturer,
        "lto_company": lto_company,
        "brand_name": brand_name,
        "generic_name": generic_name,
        "app_status": app_status,
        "app_type": app_type
    }
    
    records, total = get_main_db_records(
        db=db,
        skip=skip,
        limit=page_size,
        search=search,
        filters=filters,
        sort_by=sort_by,
        sort_order=sort_order
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": records
    }


# ✅ NEW ENDPOINT - Get unique app types with counts
@router.get("/app-types")
def get_app_types(
    status: Optional[str] = Query(None, description="Filter by decking status: 'not_decked' or 'decked'"),
    db: Session = Depends(get_db)
):
    """Get unique DB_APP_TYPE values with counts, optionally filtered by decking status"""
    query = db.query(
        MainDB.DB_APP_TYPE,
        func.count(MainDB.DB_ID).label('count')
    )
    
    # Apply status filter if provided
    if status == "not_decked":
        query = query.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query = query.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    # Get records WITH app_type (not null and not empty)
    results_with_type = query.filter(
        MainDB.DB_APP_TYPE.isnot(None),
        MainDB.DB_APP_TYPE != ""
    ).group_by(MainDB.DB_APP_TYPE)\
        .order_by(MainDB.DB_APP_TYPE)\
        .all()
    
    # Get count of records WITHOUT app_type (null or empty)
    query_no_type = db.query(func.count(MainDB.DB_ID))
    
    # Apply same status filter for no app_type records
    if status == "not_decked":
        query_no_type = query_no_type.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_type = query_no_type.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query_no_type = query_no_type.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_type = query_no_type.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    no_type_count = query_no_type.filter(
        or_(
            MainDB.DB_APP_TYPE.is_(None),
            MainDB.DB_APP_TYPE == ""
        )
    ).scalar()
    
    # Build response
    app_types = [
        {"value": app_type, "count": count} 
        for app_type, count in results_with_type
    ]
    
    # Add "No Application Type" if there are records without app_type
    if no_type_count and no_type_count > 0:
        app_types.insert(0, {"value": None, "count": no_type_count})
    
    return {"app_types": app_types}


@router.get("/prescription-types")
def get_prescription_types(
    status: Optional[str] = Query(None, description="Filter by decking status: 'not_decked' or 'decked'"),
    app_type: Optional[str] = Query(None, description="Filter by application type"),
    db: Session = Depends(get_db)
):
    """Get unique DB_PROD_CLASS_PRESCRIP values with counts, filtered by status and app_type"""
    query = db.query(
        MainDB.DB_PROD_CLASS_PRESCRIP,
        func.count(MainDB.DB_ID).label('count')
    )
    
    # Apply status filter if provided
    if status == "not_decked":
        query = query.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query = query.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    # Apply app_type filter if provided
    if app_type is not None:
        if app_type == "__EMPTY__" or app_type == "":
            query = query.filter(
                or_(
                    MainDB.DB_APP_TYPE.is_(None),
                    MainDB.DB_APP_TYPE == ""
                )
            )
        else:
            query = query.filter(MainDB.DB_APP_TYPE == app_type)
    
    # Get records WITH prescription type (not null and not empty)
    results_with_type = query.filter(
        MainDB.DB_PROD_CLASS_PRESCRIP.isnot(None),
        MainDB.DB_PROD_CLASS_PRESCRIP != ""
    ).group_by(MainDB.DB_PROD_CLASS_PRESCRIP)\
        .order_by(MainDB.DB_PROD_CLASS_PRESCRIP)\
        .all()
    
    # Get count of records WITHOUT prescription type (null or empty)
    query_no_type = db.query(func.count(MainDB.DB_ID))
    
    # Apply same status filter for no prescription type records
    if status == "not_decked":
        query_no_type = query_no_type.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_type = query_no_type.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query_no_type = query_no_type.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_type = query_no_type.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    # Apply same app_type filter for no prescription type records
    if app_type is not None:
        if app_type == "__EMPTY__" or app_type == "":
            query_no_type = query_no_type.filter(
                or_(
                    MainDB.DB_APP_TYPE.is_(None),
                    MainDB.DB_APP_TYPE == ""
                )
            )
        else:
            query_no_type = query_no_type.filter(MainDB.DB_APP_TYPE == app_type)
    
    no_type_count = query_no_type.filter(
        or_(
            MainDB.DB_PROD_CLASS_PRESCRIP.is_(None),
            MainDB.DB_PROD_CLASS_PRESCRIP == ""
        )
    ).scalar()
    
    # Build response
    prescription_types = [
        {"value": pres_type, "count": count} 
        for pres_type, count in results_with_type
    ]
    
    # Add "No Prescription Type" if there are records without prescription
    if no_type_count and no_type_count > 0:
        prescription_types.insert(0, {"value": None, "count": no_type_count})
    
    return {"prescription_types": prescription_types}


@router.get("/app-status-types")
def get_app_status_types(
    status: Optional[str] = Query(None, description="Filter by decking status: 'not_decked' or 'decked'"),
    app_type: Optional[str] = Query(None, description="Filter by application type"),
    prescription: Optional[str] = Query(None, description="Filter by prescription type"),
    db: Session = Depends(get_db)
):
    """Get unique DB_APP_STATUS values with counts, filtered by status, app_type, and prescription"""
    query = db.query(
        MainDB.DB_APP_STATUS,
        func.count(MainDB.DB_ID).label('count')
    )
    
    # Apply status filter if provided (decked/not_decked)
    if status == "not_decked":
        query = query.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query = query.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    # Apply app_type filter if provided
    if app_type is not None:
        if app_type == "__EMPTY__" or app_type == "":
            query = query.filter(
                or_(
                    MainDB.DB_APP_TYPE.is_(None),
                    MainDB.DB_APP_TYPE == ""
                )
            )
        else:
            query = query.filter(MainDB.DB_APP_TYPE == app_type)
    
    # Apply prescription filter if provided
    if prescription is not None:
        if prescription == "__EMPTY__" or prescription == "":
            query = query.filter(
                or_(
                    MainDB.DB_PROD_CLASS_PRESCRIP.is_(None),
                    MainDB.DB_PROD_CLASS_PRESCRIP == ""
                )
            )
        else:
            query = query.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    
    # Get records WITH app status (not null and not empty)
    results_with_status = query.filter(
        MainDB.DB_APP_STATUS.isnot(None),
        MainDB.DB_APP_STATUS != ""
    ).group_by(MainDB.DB_APP_STATUS)\
        .order_by(MainDB.DB_APP_STATUS)\
        .all()
    
    # Get count of records WITHOUT app status (null or empty)
    query_no_status = db.query(func.count(MainDB.DB_ID))
    
    # Apply same filters for no app status records
    if status == "not_decked":
        query_no_status = query_no_status.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_status = query_no_status.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query_no_status = query_no_status.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_status = query_no_status.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    # Apply same app_type filter
    if app_type is not None:
        if app_type == "__EMPTY__" or app_type == "":
            query_no_status = query_no_status.filter(
                or_(
                    MainDB.DB_APP_TYPE.is_(None),
                    MainDB.DB_APP_TYPE == ""
                )
            )
        else:
            query_no_status = query_no_status.filter(MainDB.DB_APP_TYPE == app_type)
    
    # Apply same prescription filter
    if prescription is not None:
        if prescription == "__EMPTY__" or prescription == "":
            query_no_status = query_no_status.filter(
                or_(
                    MainDB.DB_PROD_CLASS_PRESCRIP.is_(None),
                    MainDB.DB_PROD_CLASS_PRESCRIP == ""
                )
            )
        else:
            query_no_status = query_no_status.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    
    no_status_count = query_no_status.filter(
        or_(
            MainDB.DB_APP_STATUS.is_(None),
            MainDB.DB_APP_STATUS == ""
        )
    ).scalar()
    
    # Build response
    app_status_types = [
        {"value": app_status, "count": count} 
        for app_status, count in results_with_status
    ]
    
    # Add "No Application Status" if there are records without status
    if no_status_count and no_status_count > 0:
        app_status_types.insert(0, {"value": None, "count": no_status_count})
    
    return {"app_status_types": app_status_types}


@router.get("/establishment-categories")
def get_establishment_categories(
    status: Optional[str] = Query(None, description="Filter by decking status: 'not_decked', 'decked', or null for all"),
    db: Session = Depends(get_db)
):
    """Get unique DB_EST_CAT (Establishment Category) values with counts"""
    query = db.query(
        MainDB.DB_EST_CAT,
        func.count(MainDB.DB_ID).label('count')
    )
    
    # Apply status filter if provided
    if status == "not_decked":
        query = query.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query = query.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query = query.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    # If status is None, no additional filter is applied (get all records)
    
    # Get records WITH category (not null and not empty)
    results_with_category = query.filter(
        MainDB.DB_EST_CAT.isnot(None),
        MainDB.DB_EST_CAT != ""
    ).group_by(MainDB.DB_EST_CAT)\
        .order_by(MainDB.DB_EST_CAT)\
        .all()
    
    # Get count of records WITHOUT category (null or empty)
    query_no_category = db.query(func.count(MainDB.DB_ID))
    
    # Apply same status filter for no category records
    if status == "not_decked":
        query_no_category = query_no_category.outerjoin(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_category = query_no_category.filter(
            or_(
                ApplicationDelegation.DB_EVALUATOR.is_(None),
                ApplicationDelegation.DB_EVALUATOR == "",
                ApplicationDelegation.DB_EVALUATOR == "N/A"
            )
        )
    elif status == "decked":
        query_no_category = query_no_category.join(ApplicationDelegation, MainDB.DB_ID == ApplicationDelegation.DB_MAIN_ID)
        query_no_category = query_no_category.filter(
            ApplicationDelegation.DB_EVALUATOR.isnot(None),
            ApplicationDelegation.DB_EVALUATOR != "",
            ApplicationDelegation.DB_EVALUATOR != "N/A"
        )
    
    no_category_count = query_no_category.filter(
        or_(
            MainDB.DB_EST_CAT.is_(None),
            MainDB.DB_EST_CAT == ""
        )
    ).scalar()
    
    # Build response
    categories = [
        {"value": category, "count": count} 
        for category, count in results_with_category
    ]
    
    # Add "No Category" if there are records without category
    if no_category_count and no_category_count > 0:
        categories.insert(0, {"value": None, "count": no_category_count})
    
    return {"categories": categories}

@router.get("/logs/{main_id}", response_model=List[ApplicationLogResponse])
def get_logs(
    main_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get application logs for a specific MainDB record"""
    skip = (page - 1) * page_size
    logs, _ = get_application_logs(db=db, main_id=main_id, skip=skip, limit=page_size)
    return logs


@router.get("/summary", response_model=MainDBSummary)
def get_summary(db: Session = Depends(get_db)):
    """Get summary statistics"""
    return crud.get_main_db_summary(db)


@router.get("/filters/{field}")
def get_filter_options(field: str, db: Session = Depends(get_db)):
    """Get unique values for a field (for dropdown filters)"""
    values = crud.get_unique_values(db, field)
    return {"field": field, "values": values}

@router.post("/upload-excel")
async def upload_excel(
    file: UploadFile = File(...), 
    username: str = Query("system"), 
    db: Session = Depends(get_db)
):
    """Upload an Excel file and insert records into MainDB and ApplicationDelegation"""
    print("🚀 Starting Excel upload process...")
    
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be .xls or .xlsx")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read Excel file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Excel file is empty")

    # Convert datetime columns to strings for MainDB fields
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else None)
        elif df[col].dtype == 'object':
            if df[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
                df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%d") if isinstance(x, pd.Timestamp) else x)
    
    print(f"📊 Total rows in Excel: {len(df)}")
    success, errors = 0, []

    for index, row in df.iterrows():
        try:
            record_data = {}
            delegation_data = {}

            # Map Excel to MainDB columns with proper type handling
            for excel_col, db_col in COLUMN_MAPPING.items():
                raw_value = row.get(excel_col)
                
                if pd.isna(raw_value) or raw_value is None:
                    record_data[db_col] = None
                elif isinstance(raw_value, (int, float, np.integer, np.floating)):
                    # ✅ Handle different numeric field types
                    if db_col in NUMERIC_STRING_FIELDS:
                        # Fee, LRF, SURC, Total - store as string
                        record_data[db_col] = str(int(raw_value))
                    elif db_col in INTEGER_FIELDS:
                        # DTN, Is in PM, Timeline - store as integer
                        record_data[db_col] = int(raw_value)
                    else:
                        # Everything else becomes string
                        record_data[db_col] = str(raw_value)
                else:
                    record_data[db_col] = str(raw_value).strip() if isinstance(raw_value, str) else str(raw_value)

            # Map Excel to ApplicationDelegation columns with proper date handling
            for excel_col, db_col in DELEGATION_COLUMN_MAPPING.items():
                raw_value = row.get(excel_col)
                
                # Handle date fields specially
                if db_col in DELEGATION_DATE_FIELDS:
                    parsed_date = parse_date_value(raw_value)
                    delegation_data[db_col] = parsed_date
                else:
                    # Handle text fields
                    if pd.isna(raw_value) or raw_value is None:
                        delegation_data[db_col] = None
                    elif isinstance(raw_value, str):
                        delegation_data[db_col] = raw_value.strip()
                    elif isinstance(raw_value, (int, float, np.integer, np.floating)):
                        delegation_data[db_col] = None  # Skip numeric values for text fields
                    else:
                        delegation_data[db_col] = str(raw_value)

            # Add metadata
            record_data["DB_USER_UPLOADER"] = username
            record_data["DB_DATE_EXCEL_UPLOAD"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create MainDB record
            db_record = crud.create_main_db_record(db, MainDBCreate(**record_data))

            # Always create ApplicationDelegation record (1:1)
            delegation_data["DB_MAIN_ID"] = db_record.DB_ID
            
            # Ensure all delegation fields exist with None defaults
            for col in DELEGATION_COLUMN_MAPPING.values():
                delegation_data.setdefault(col, None)

            delegation_record = ApplicationDelegation(**delegation_data)
            db.add(delegation_record)
            db.commit()
            print(f"  ✅ Created delegation record for MainDB ID {db_record.DB_ID}")

            success += 1

        except Exception as e:
            print(f"❌ Error on row {index + 2}: {str(e)}")
            import traceback
            traceback.print_exc()
            errors.append({
                "row": index + 2,
                "error": str(e),
                "data": {k: str(v)[:50] for k, v in row.to_dict().items() if pd.notna(v)}
            })

    print(f"✅ Upload complete: {success} success, {len(errors)} errors")
    
    return {
        "success": True,
        "message": f"Upload complete: {success} records inserted successfully",
        "stats": {"total": len(df), "success": success, "errors": len(errors)},
        "errors": errors[:10]  # return first 10 errors
    }


@router.get("/download-template")
async def download_template():
    """Download Excel template with proper column headers including delegation columns"""
    try:
        # Combine both MainDB and Delegation columns
        all_columns = {**COLUMN_MAPPING, **DELEGATION_COLUMN_MAPPING}
        template_data = {col: [""] for col in all_columns.keys()}
        df = pd.DataFrame(template_data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Template")
            
            # Optional: Add a second sheet with instructions
            instructions = pd.DataFrame({
                "Column Group": [
                    "Main Database Columns",
                    "Application Delegation Columns",
                    "Date Format Instructions",
                    "Numeric Field Instructions"
                ],
                "Description": [
                    "Columns from DTN to 'Timeline Citizen Charter' are for main database records",
                    "Columns from Decker to 'Date Releasing Officer End' are for application delegation tracking",
                    "For date fields, use formats like: 2026-01-02, Jan 2 2026, 01/02/2026, etc.",
                    "Timeline Citizen Charter should be a whole number (e.g., 30, 45, 60)"
                ],
                "Note": [
                    "All main database columns are optional",
                    "Delegation columns are optional. Fill only if you have delegation data.",
                    "Date fields will be automatically parsed. Leave empty if no date.",
                    "Enter numbers without decimals for timeline fields."
                ]
            })
            instructions.to_excel(writer, index=False, sheet_name="Instructions")
        
        output.seek(0)
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=main_db_template.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")


@router.get("/upload-history")
async def get_upload_history(
    limit: int = Query(50, ge=1, le=100), 
    db: Session = Depends(get_db)
):
    """Get upload history grouped by user and date"""
    try:
        history = crud.get_upload_history(db=db, limit=limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch upload history: {str(e)}")

@router.get("/export-filtered")
async def export_filtered_records(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    prescription: Optional[str] = Query(None),
    prescription_not: Optional[str] = Query(None),
    dtn: Optional[int] = Query(None),
    manufacturer: Optional[str] = Query(None),
    lto_company: Optional[str] = Query(None),
    brand_name: Optional[str] = Query(None),
    generic_name: Optional[str] = Query(None),
    app_status: Optional[str] = Query(None),
    app_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export filtered records to Excel"""
    try:
        print(f"📥 Export request received with params: status={status}, app_type={app_type}, search={search}")
        
        # Build filters
        filters = {
            "status": status,
            "category": category,
            "prescription": prescription,
            "prescription_not": prescription_not,
            "dtn": dtn,
            "manufacturer": manufacturer,
            "lto_company": lto_company,
            "brand_name": brand_name,
            "generic_name": generic_name,
            "app_status": app_status,
            "app_type": app_type
        }
        
        # Get ALL filtered records (no pagination)
        records, total = get_main_db_records(
            db=db,
            skip=0,
            limit=100000,
            search=search,
            filters=filters,
            sort_by="DB_DATE_EXCEL_UPLOAD",
            sort_order="desc"
        )
        
        print(f"📊 Found {total} records to export")
        
        if not records:
            raise HTTPException(status_code=404, detail="No records found to export")
        
        # Convert records to DataFrame
        data_for_export = []
        for record in records:
            delegation = record.application_delegation if hasattr(record, 'application_delegation') else None
            
            row_data = {
                "DTN": record.DB_DTN,
                "Est. Category": record.DB_EST_CAT,
                "LTO Company": record.DB_EST_LTO_COMP,
                "LTO Address": record.DB_EST_LTO_ADD,
                "Email": record.DB_EST_EADD,
                "TIN": record.DB_EST_TIN,
                "Contact No.": record.DB_EST_CONTACT_NO,
                "LTO No.": record.DB_EST_LTO_NO,
                "Validity": record.DB_EST_VALIDITY,
                "Brand Name": record.DB_PROD_BR_NAME,
                "Generic Name": record.DB_PROD_GEN_NAME,
                "Dosage Strength": record.DB_PROD_DOS_STR,
                "Dosage Form": record.DB_PROD_DOS_FORM,
                "Prescription": record.DB_PROD_CLASS_PRESCRIP,
                "Essential Drug": record.DB_PROD_ESS_DRUG_LIST,
                "Pharma Category": record.DB_PROD_PHARMA_CAT,
                "Manufacturer": record.DB_PROD_MANU,
                "Manufacturer Address": record.DB_PROD_MANU_ADD,
                "Manufacturer TIN": record.DB_PROD_MANU_TIN,
                "Manufacturer LTO No.": record.DB_PROD_MANU_LTO_NO,
                "Manufacturer Country": record.DB_PROD_MANU_COUNTRY,
                "Registration No.": record.DB_REG_NO,
                "App Type": record.DB_APP_TYPE,
                "Mother App Type": record.DB_MOTHER_APP_TYPE,
                "App Status": record.DB_APP_STATUS,
                "Fee": record.DB_FEE,
                "LRF": record.DB_LRF,
                "SURC": record.DB_SURC,
                "Total": record.DB_TOTAL,
                "OR No.": record.DB_OR_NO,
                "Date Issued": record.DB_DATE_ISSUED,
                "Date Received FDAC": record.DB_DATE_RECEIVED_FDAC,
                "Date Received Central": record.DB_DATE_RECEIVED_CENT,
                "Date Deck": record.DB_DATE_DECK,
                "Date Released": record.DB_DATE_RELEASED,
                "User Uploader": record.DB_USER_UPLOADER,
                "Date Excel Upload": str(record.DB_DATE_EXCEL_UPLOAD) if record.DB_DATE_EXCEL_UPLOAD else None,
            }
            
            if delegation:
                row_data.update({
                    "Evaluator": delegation.DB_EVALUATOR,
                    "Evaluator Decision": delegation.DB_EVAL_DECISION,
                    "Evaluator Remarks": delegation.DB_EVAL_REMARKS,
                    "Date Eval End": str(delegation.DB_DATE_EVAL_END) if delegation.DB_DATE_EVAL_END else None,
                    "Decker": delegation.DB_DECKER,
                    "Decker Decision": delegation.DB_DECKER_DECISION,
                    "Decker Remarks": delegation.DB_DECKER_REMARKS,
                    "Date Decked End": str(delegation.DB_DATE_DECKED_END) if delegation.DB_DATE_DECKED_END else None,
                    "Checker": delegation.DB_CHECKER,
                    "Checker Decision": delegation.DB_CHECKER_DECISION,
                    "Date Checker End": str(delegation.DB_DATE_CHECKER_END) if delegation.DB_DATE_CHECKER_END else None,
                })
            
            data_for_export.append(row_data)
        
        print(f"📝 Prepared {len(data_for_export)} rows for export")
        
        df = pd.DataFrame(data_for_export)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Filtered Records')
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filter_description = []
        if app_type:
            filter_description.append(f"{app_type}")
        if status:
            filter_description.append(f"{status}")
        
        filename_parts = ["main_db_export", timestamp]
        if filter_description:
            filename_parts.insert(1, "_".join(filter_description))
        
        filename = "_".join(filename_parts) + ".xlsx"
        
        print(f"✅ Export successful: {filename}")
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Export error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to export records: {str(e)}")

@router.get("/{record_id}", response_model=MainDBResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    """Get a single record by ID"""
    record = crud.get_main_db_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Record with ID {record_id} not found"
        )
    return record


@router.post("/", response_model=MainDBResponse, status_code=status.HTTP_201_CREATED)
def create_record(record: MainDBCreate, db: Session = Depends(get_db)):
    """Create a new record"""
    return crud.create_main_db_record(db, record)


@router.post("/bulk", response_model=List[MainDBResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_records(records: List[MainDBCreate], db: Session = Depends(get_db)):
    """Bulk create records"""
    return crud.bulk_create_main_db_records(db, records)


@router.put("/{record_id}", response_model=MainDBResponse)
def update_record(
    record_id: int, 
    record_update: MainDBUpdate, 
    db: Session = Depends(get_db)
):
    """Update an existing record"""
    updated_record = crud.update_main_db_record(db, record_id, record_update)
    if not updated_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Record with ID {record_id} not found"
        )
    return updated_record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int, 
    hard_delete: bool = Query(False, description="Permanently delete (default: soft delete)"), 
    db: Session = Depends(get_db)
):
    """Delete a record (soft delete by default)"""
    if hard_delete:
        success = crud.hard_delete_main_db_record(db, record_id)
    else:
        success = crud.delete_main_db_record(db, record_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Record with ID {record_id} not found"
        )
    return None


@router.post("/{record_id}/restore", response_model=MainDBResponse)
def restore_record(record_id: int, db: Session = Depends(get_db)):
    """Restore a soft-deleted record"""
    record = crud.get_main_db_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Record with ID {record_id} not found"
        )
    record.DB_TRASH = None
    record.DB_TRASH_DATE_ENCODED = None
    db.commit()
    db.refresh(record)
    return record

