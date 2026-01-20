"""
Application Logs Routes
Track workflow steps and decisions for applications
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import application_logs as crud_logs
from app.schemas.application_logs import (
    ApplicationLogCreate,
    ApplicationLogUpdate,
    ApplicationLogResponse
)
from app.models.user import User

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
        "accomplished_date": "2025-01-19T14:30:00"
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


# ✅ NEW: Bulk create application logs
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
            "accomplished_date": "2025-01-19T14:30:00"
        },
        {
            "main_db_id": 124,
            "application_step": "Decking",
            "user_name": "decker001",
            "application_status": "For Evaluation",
            "application_decision": "For Evaluation",
            "application_remarks": "All requirements met",
            "accomplished_date": "2025-01-19T14:30:00"
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