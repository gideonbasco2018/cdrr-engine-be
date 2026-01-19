from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
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
from app.models.application_delegation import ApplicationDelegation

router = APIRouter(
    prefix="/api/main-db",
    tags=["Main Database"]
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
    "Is in PM": "DB_IS_IN_PM"
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
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort_by: str = Query("DB_DATE_EXCEL_UPLOAD"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get paginated list of main database records"""
    skip = (page - 1) * page_size
    records, total = get_main_db_records(
        db=db,
        skip=skip,
        limit=page_size,
        search=search,
        status=status,
        category=category,
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

            # Map Excel to MainDB columns
            for excel_col, db_col in COLUMN_MAPPING.items():
                raw_value = row.get(excel_col)
                if pd.isna(raw_value) or raw_value is None:
                    record_data[db_col] = None
                elif isinstance(raw_value, (int, float, np.integer, np.floating)):
                    if db_col in NUMERIC_STRING_FIELDS:
                        record_data[db_col] = str(int(raw_value))
                    else:
                        record_data[db_col] = int(raw_value) if db_col in {'DB_DTN', 'DB_IS_IN_PM'} else str(raw_value)
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
                    "Date Format Instructions"
                ],
                "Description": [
                    "Columns from DTN to 'Is in PM' are for main database records",
                    "Columns from Decker to 'Date Releasing Officer End' are for application delegation tracking",
                    "For date fields, use formats like: 2026-01-02, Jan 2 2026, 01/02/2026, etc."
                ],
                "Note": [
                    "All main database columns are optional",
                    "Delegation columns are optional. Fill only if you have delegation data.",
                    "Date fields will be automatically parsed. Leave empty if no date."
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