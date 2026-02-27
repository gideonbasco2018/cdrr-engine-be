"""
Application Logs Routes
Track workflow steps and decisions for applications
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import application_logs as crud_logs
from app.schemas.application_logs import (
    ApplicationLogCreate,
    ApplicationLogUpdate,
    ApplicationLogResponse
)
from app.models.user import User
from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs

router = APIRouter(
    prefix="/api/application-logs",
    tags=["Application Logs"]
)


@router.post("/", response_model=ApplicationLogResponse, status_code=status.HTTP_201_CREATED)
def create_application_log(
    log_in: ApplicationLogCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new application log entry
    
    This endpoint is called whenever an action is performed on an application:
    - Decking
    - Evaluation
    - Checking
    - Supervisor review
    - QA review
    - Director approval
    - Releasing
    
    Example request body:
```json
    {
        "main_db_id": 123,
        "application_step": "Evaluation",
        "user_name": "eval001",
        "application_status": "For Checking",
        "application_decision": "For Checking",
        "application_remarks": "All documents verified. Ready for checking.",
        "start_date": "2025-01-19T10:00:00",
        "accomplished_date": "2025-01-19T14:30:00",
        "del_index": null,
        "del_previous": null,
        "del_last_index": null
    }
```
    """
    try:
        log = crud_logs.create(db, log_in=log_in)
        return log
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application log: {str(e)}"
        )


@router.post("/bulk", response_model=List[ApplicationLogResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_application_logs(
    logs_in: List[ApplicationLogCreate],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create multiple application log entries at once
    
    Useful for bulk operations like:
    - Bulk decking multiple applications
    - Batch processing workflows
    
    Example request body:
```json
    [
        {
            "main_db_id": 123,
            "application_step": "Decking",
            "user_name": "decker001",
            "application_status": "For Evaluation",
            "application_decision": "For Evaluation",
            "application_remarks": "Documents complete",
            "accomplished_date": "2025-01-19T14:30:00",
            "del_index": null,
            "del_previous": null,
            "del_last_index": null
        },
        {
            "main_db_id": 124,
            "application_step": "Decking",
            "user_name": "decker001",
            "application_status": "For Evaluation",
            "application_decision": "For Evaluation",
            "application_remarks": "All requirements met",
            "accomplished_date": "2025-01-19T14:30:00",
            "del_index": null,
            "del_previous": null,
            "del_last_index": null
        }
    ]
```
    
    Returns:
    - List of created log entries
    - Partial success: If some logs fail, returns only successful ones
    """
    if not logs_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No logs provided"
        )
    
    if len(logs_in) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create more than 100 logs at once"
        )
    
    created_logs = []
    errors = []
    
    for idx, log_in in enumerate(logs_in):
        try:
            log = crud_logs.create(db, log_in=log_in)
            created_logs.append(log)
        except Exception as e:
            errors.append({
                "index": idx,
                "main_db_id": log_in.main_db_id,
                "error": str(e)
            })
    
    # If all failed
    if not created_logs:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create all logs. Errors: {errors}"
        )
    
    # If some failed, log warning but return successful ones
    if errors:
        print(f"⚠️ Partial success: {len(created_logs)}/{len(logs_in)} logs created. Errors: {errors}")
    
    return created_logs


@router.get("/main-db/{main_db_id}", response_model=List[ApplicationLogResponse])
def get_logs_by_main_db(
    main_db_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all logs for a specific application (main_db record)
    
    Returns logs ordered by created_at (newest first)
    """
    logs = crud_logs.get_by_main_db_id(db, main_db_id=main_db_id)
    return logs


@router.get("/main-db/{main_db_id}/step/{step}", response_model=List[ApplicationLogResponse])
def get_logs_by_step(
    main_db_id: int,
    step: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get logs for a specific workflow step
    
    Common steps:
    - Decking
    - Evaluation
    - Checking
    - Supervisor
    - QA
    - Director
    - Releasing
    """
    logs = crud_logs.get_by_step(db, main_db_id=main_db_id, step=step)
    return logs


@router.get("/{log_id}", response_model=ApplicationLogResponse)
def get_log(
    log_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific application log by ID"""
    log = crud_logs.get_by_id(db, log_id=log_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found"
        )
    
    return log


@router.put("/{log_id}", response_model=ApplicationLogResponse)
def update_log(
    log_id: int,
    log_in: ApplicationLogUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update an application log"""
    log = crud_logs.update(db, log_id=log_id, log_in=log_in)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found"
        )
    
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(
    log_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an application log"""
    success = crud_logs.delete(db, log_id=log_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found"
        )
    
    return None


@router.get("/main-db/{main_db_id}/last-index")
def get_last_index(
    main_db_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get the latest del_index for an application.
    Returns 0 if no logs exist.
    """
    try:
        last_index = crud_logs.get_last_index(db, main_db_id)
        return {
            "main_db_id": main_db_id,
            "last_index": last_index,
            "next_index": last_index + 1
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch last index: {str(e)}"
        )


# ══════════════════════════════════════════════════════════════════════
#  NEW — Get logs by DTN (query param)
#  GET /api/application-logs?dtn=20210927134427
# ══════════════════════════════════════════════════════════════════════
@router.get("/", response_model=List[ApplicationLogResponse])
def get_logs_by_dtn(
    dtn: int = Query(..., description="Document Tracking Number (DB_DTN)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all application logs for a given DTN.

    1. Resolves DB_DTN → DB_ID from main_db
    2. Returns all application_logs rows for that main_db_id,
       ordered by del_index DESC then created_at DESC so the
       latest step is always shown first.

    Example:
        GET /api/application-logs?dtn=20210927134427
    """
    # Step 1: find the main_db record that owns this DTN
    main_record = (
        db.query(MainDB)
        .filter(MainDB.DB_DTN == dtn)
        .first()
    )

    if not main_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No main_db record found for DTN {dtn}"
        )

    # Step 2: fetch logs — latest first
    logs = (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.main_db_id == main_record.DB_ID)
        .order_by(
            ApplicationLogs.del_index.desc(),
            ApplicationLogs.created_at.desc()
        )
        .all()
    )

    return logs