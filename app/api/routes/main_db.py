"""
FastAPI Router for Main DB CRUD Operations
Endpoints for pharmaceutical reports management
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
import math

from app.db.session import get_db
from app.schemas.main_db import (
    MainDBCreate,
    MainDBUpdate,
    MainDBResponse,
    MainDBListResponse,
    MainDBSummary
)
from app.crud import main_db as crud

router = APIRouter(
    prefix="/api/main-db",
    tags=["Main Database"],
    responses={404: {"description": "Not found"}}
)


@router.get("/", response_model=MainDBListResponse)
def get_records(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Search term"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("DB_DATE_EXCEL_UPLOAD", description="Sort by field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of records with filtering and searching
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of records per page (max 100)
    - **search**: Search across DTN, company name, brand name, generic name, reg no
    - **status**: Filter by application status (Approved, Pending, Rejected)
    - **category**: Filter by establishment category (Pharmacy, Hospital, Drugstore)
    - **sort_by**: Field to sort by
    - **sort_order**: asc or desc
    """
    skip = (page - 1) * page_size
    
    records, total = crud.get_main_db_records(
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


@router.get("/summary", response_model=MainDBSummary)
def get_summary(db: Session = Depends(get_db)):
    """
    Get summary statistics
    
    Returns counts by status, category, and recent uploads
    """
    return crud.get_main_db_summary(db)


@router.get("/filters/{field}")
def get_filter_options(
    field: str,
    db: Session = Depends(get_db)
):
    """
    Get unique values for a field (for dropdown filters)
    
    - **field**: Field name (e.g., DB_APP_STATUS, DB_EST_CAT)
    """
    values = crud.get_unique_values(db, field)
    return {"field": field, "values": values}


@router.get("/{record_id}", response_model=MainDBResponse)
def get_record(
    record_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single record by ID
    """
    record = crud.get_main_db_record(db, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Record with ID {record_id} not found"
        )
    return record


@router.post("/", response_model=MainDBResponse, status_code=status.HTTP_201_CREATED)
def create_record(
    record: MainDBCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new record
    """
    return crud.create_main_db_record(db, record)


@router.post("/bulk", response_model=List[MainDBResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_records(
    records: List[MainDBCreate],
    db: Session = Depends(get_db)
):
    """
    Bulk create records (for Excel import)
    
    - **records**: List of records to create
    """
    return crud.bulk_create_main_db_records(db, records)


@router.put("/{record_id}", response_model=MainDBResponse)
def update_record(
    record_id: int,
    record_update: MainDBUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing record
    """
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
    """
    Delete a record
    
    - **hard_delete**: If True, permanently delete. If False (default), soft delete
    """
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
def restore_record(
    record_id: int,
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted record
    """
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
