from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
import pandas as pd
import io
from datetime import datetime
import math
import numpy as np

from app.db.session import get_db
from app.schemas.main_db import MainDBCreate, MainDBUpdate, MainDBResponse, MainDBListResponse, MainDBSummary
from app.crud import main_db as crud

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

# Date and numeric field definitions
DATE_FIELDS = {
    'DB_EST_VALIDITY', 'DB_EXPIRY_DATE', 'DB_CPR_VALIDITY', 
    'DB_DATE_ISSUED', 'DB_DATE_DECK', 'DB_DATE_RECEIVED_FDAC',
    'DB_DATE_RECEIVED_CENT', 'DB_SECPA_EXP_DATE', 'DB_SECPA_ISSUED_ON',
    'DB_DATE_REMARKS', 'DB_DATE_RELEASED', 'DB_DATE_EXCEL_UPLOAD'
}

NUMERIC_FIELDS = {'DB_FEE', 'DB_LRF', 'DB_SURC', 'DB_TOTAL'}

# ---------------------
# Helper Functions
# ---------------------
def convert_pandas_value(value, field_name):
    """
    Convert pandas types to Python native types based on field type
    """
    # Handle None and NaN first
    if value is None or pd.isna(value):
        return None
    
    # Handle date fields
    if field_name in DATE_FIELDS:
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.strftime("%Y-%m-%d")
        elif isinstance(value, (int, float)):
            try:
                date_val = datetime(1899, 12, 30) + pd.to_timedelta(value, unit="D")
                return date_val.strftime("%Y-%m-%d")
            except:
                return None
        elif isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        else:
            return None
    
    # Handle numeric fields that should be strings
    elif field_name in NUMERIC_FIELDS:
        if isinstance(value, (int, float)):
            try:
                return str(int(float(value)))
            except:
                return None
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped:
                try:
                    return str(int(float(stripped)))
                except:
                    return stripped
            return None
        else:
            return None
    
    # Handle DB_IS_IN_PM (should be int)
    elif field_name == 'DB_IS_IN_PM':
        try:
            return int(float(value))
        except:
            return 0
    
    # Handle DB_DTN (should be int)
    elif field_name == 'DB_DTN':
        if isinstance(value, (int, float)):
            try:
                return int(float(value))
            except:
                return None
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped:
                try:
                    return int(float(stripped))
                except:
                    return None
            return None
        else:
            return None
    
    # Handle regular string fields
    else:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return str(value) if value else None


# ---------------------
# CRUD Endpoints
# ---------------------
@router.get("/", response_model=MainDBListResponse)
def get_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Search term"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("DB_DATE_EXCEL_UPLOAD", description="Sort by field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """Get paginated list of records with filtering and searching"""
    skip = (page - 1) * page_size
    records, total = crud.get_main_db_records(
        db=db, skip=skip, limit=page_size,
        search=search, status=status,
        category=category, sort_by=sort_by, sort_order=sort_order
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages, "data": records}

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
async def upload_excel(file: UploadFile = File(...), username: str = Query("system"), db: Session = Depends(get_db)):
    """Upload an Excel file and insert records into the database"""
    print("🚀🚀🚀 NEWEST CODE VERSION 2.0 🚀🚀🚀")
    
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()
    df = pd.read_excel(io.BytesIO(contents))

    if df.empty:
        raise HTTPException(status_code=400, detail="Excel file is empty")

    # ===== CONVERT ALL DATAFRAME COLUMNS IMMEDIATELY =====
    print("🔄 Converting DataFrame columns...")
    for col in df.columns:
        print(f"  Checking column: {col[:30]}...")
        # Convert Timestamp columns to strings
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            print(f"    ✅ Found datetime column, converting...")
            df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else None)
        # Check for Timestamps in object columns
        elif df[col].dtype == 'object':
            if df[col].apply(lambda x: isinstance(x, pd.Timestamp)).any():
                print(f"    ✅ Found Timestamps in object column, converting...")
                df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%d") if isinstance(x, pd.Timestamp) else x)
    
    print(f"📊 Total rows in Excel: {len(df)}")
    success, errors = 0, []

    for index, row in df.iterrows():
        try:
            record_data = {}
            
            # Process each Excel column - values should already be converted
            for excel_col, db_col in COLUMN_MAPPING.items():
                raw_value = row.get(excel_col)
                
                print(f"Row {index+2}, {db_col}: type={type(raw_value).__name__}, value={repr(raw_value)[:30]}")
                
                # Handle NaN/None
                if pd.isna(raw_value) or raw_value is None:
                    record_data[db_col] = None
                    continue
                
                # Handle numeric values that should be strings
                if isinstance(raw_value, (int, float, np.integer, np.floating)):
                    if db_col in {'DB_FEE', 'DB_LRF', 'DB_SURC', 'DB_TOTAL'}:
                        record_data[db_col] = str(int(raw_value))
                    elif db_col in {'DB_DTN', 'DB_IS_IN_PM'}:
                        record_data[db_col] = int(raw_value)
                    else:
                        record_data[db_col] = str(raw_value)
                    continue
                
                # Handle strings
                if isinstance(raw_value, str):
                    stripped = raw_value.strip()
                    record_data[db_col] = stripped if stripped else None
                    continue
                
                # This should NEVER be reached if conversion worked
                print(f"⚠️⚠️⚠️ UNEXPECTED TYPE: {type(raw_value)} for {db_col}")
                record_data[db_col] = str(raw_value)

            # Add metadata
            record_data["DB_USER_UPLOADER"] = username
            record_data["DB_DATE_EXCEL_UPLOAD"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create record
            print(f"📝 Creating record for row {index + 2}...")
            crud.create_main_db_record(db, MainDBCreate(**record_data))
            success += 1
            print(f"✅ Row {index + 2} inserted successfully")

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
        "errors": errors[:10]
    }


@router.get("/download-template")
async def download_template():
    """Download Excel template with proper column headers"""
    try:
        template_data = {col: [""] for col in COLUMN_MAPPING.keys()}
        df = pd.DataFrame(template_data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Template")
        output.seek(0)
        return StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=main_db_template.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")

@router.get("/upload-history")
async def get_upload_history(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record with ID {record_id} not found")
    return record

@router.post("/", response_model=MainDBResponse, status_code=status.HTTP_201_CREATED)
def create_record(record: MainDBCreate, db: Session = Depends(get_db)):
    """Create a new record"""
    return crud.create_main_db_record(db, record)

@router.post("/bulk", response_model=List[MainDBResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_records(records: List[MainDBCreate], db: Session = Depends(get_db)):
    """Bulk create records (for Excel import)"""
    return crud.bulk_create_main_db_records(db, records)

@router.put("/{record_id}", response_model=MainDBResponse)
def update_record(record_id: int, record_update: MainDBUpdate, db: Session = Depends(get_db)):
    """Update an existing record"""
    updated_record = crud.update_main_db_record(db, record_id, record_update)
    if not updated_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record with ID {record_id} not found")
    return updated_record

@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int, 
    hard_delete: bool = Query(False, description="Permanently delete (default: soft delete)"), 
    db: Session = Depends(get_db)
):
    """Delete a record"""
    if hard_delete:
        success = crud.hard_delete_main_db_record(db, record_id)
    else:
        success = crud.delete_main_db_record(db, record_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record with ID {record_id} not found")
    return None

@router.post("/{record_id}/restore", response_model=MainDBResponse)
def restore_record(record_id: int, db: Session = Depends(get_db)):
    """Restore a soft-deleted record"""
    record = crud.get_main_db_record(db, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record with ID {record_id} not found")
    record.DB_TRASH = None
    record.DB_TRASH_DATE_ENCODED = None
    db.commit()
    db.refresh(record)
    return record