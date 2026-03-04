"""
CRUD Operations for Application Logs
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime

from app.models.application_logs import ApplicationLogs
from app.schemas.application_logs import ApplicationLogCreate, ApplicationLogUpdate


def create(db: Session, log_in: ApplicationLogCreate) -> ApplicationLogs:
    """
    Create a new application log entry
    """
    db_log = ApplicationLogs(
        main_db_id=log_in.main_db_id,
        application_step=log_in.application_step,
        user_name=log_in.user_name,
        application_status=log_in.application_status,
        application_decision=log_in.application_decision,
        application_remarks=log_in.application_remarks,
        start_date=log_in.start_date,
        accomplished_date=log_in.accomplished_date,
        del_index=log_in.del_index,
        del_previous=log_in.del_previous,
        del_last_index=log_in.del_last_index,
        del_thread=log_in.del_thread,
        deadline_date = log_in.deadline_date,
        working_days  = log_in.working_days
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    
    return db_log


def create_bulk(db: Session, logs_in: List[ApplicationLogCreate]) -> List[ApplicationLogs]:
    """
    Create multiple application log entries in a single transaction
    
    If any log fails, all are rolled back (all-or-nothing)
    
    Args:
        db: Database session
        logs_in: List of ApplicationLogCreate objects
    
    Returns:
        List of created ApplicationLogs objects
    
    Raises:
        Exception: If any log creation fails
    """
    try:
        db_logs = []
        
        for log_in in logs_in:
            db_log = ApplicationLogs(
                main_db_id=log_in.main_db_id,
                application_step=log_in.application_step,
                user_name=log_in.user_name,
                application_status=log_in.application_status,
                application_decision=log_in.application_decision,
                application_remarks=log_in.application_remarks,
                start_date=log_in.start_date,
                accomplished_date=log_in.accomplished_date,
                del_index=log_in.del_index,
                del_previous=log_in.del_previous,
                del_last_index=log_in.del_last_index
            )
            db.add(db_log)
            db_logs.append(db_log)
        
        # Commit all at once
        db.commit()
        
        # Refresh all logs to get their IDs and timestamps
        for db_log in db_logs:
            db.refresh(db_log)
        
        return db_logs
        
    except Exception as e:
        # Rollback if any error occurs
        db.rollback()
        raise e


def get_by_id(db: Session, log_id: int) -> Optional[ApplicationLogs]:
    """Get application log by ID"""
    return db.query(ApplicationLogs).filter(ApplicationLogs.id == log_id).first()


def get_by_main_db_id(db: Session, main_db_id: int) -> List[ApplicationLogs]:
    """
    Get all logs for a specific main_db record
    Returns logs ordered by created_at (newest first)
    """
    return db.query(ApplicationLogs).filter(
        ApplicationLogs.main_db_id == main_db_id
    ).order_by(
        ApplicationLogs.created_at.desc()
    ).all()


def get_by_step(db: Session, main_db_id: int, step: str) -> List[ApplicationLogs]:
    """Get logs for a specific step (e.g., 'Decking', 'Evaluation')"""
    return db.query(ApplicationLogs).filter(
        ApplicationLogs.main_db_id == main_db_id,
        ApplicationLogs.application_step == step
    ).order_by(
        ApplicationLogs.created_at.desc()
    ).all()


def get_all_by_step(db: Session, step: str, limit: int = 100) -> List[ApplicationLogs]:
    """
    Get all logs for a specific step across all applications
    Useful for reporting/analytics
    """
    return db.query(ApplicationLogs).filter(
        ApplicationLogs.application_step == step
    ).order_by(
        ApplicationLogs.created_at.desc()
    ).limit(limit).all()


def get_by_user(db: Session, user_name: str, limit: int = 100) -> List[ApplicationLogs]:
    """
    Get all logs for a specific user
    Useful for tracking user activity
    """
    return db.query(ApplicationLogs).filter(
        ApplicationLogs.user_name == user_name
    ).order_by(
        ApplicationLogs.created_at.desc()
    ).limit(limit).all()


def get_by_date_range(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    step: Optional[str] = None
) -> List[ApplicationLogs]:
    """
    Get logs within a date range
    Useful for reporting and analytics
    """
    query = db.query(ApplicationLogs).filter(
        ApplicationLogs.created_at >= start_date,
        ApplicationLogs.created_at <= end_date
    )
    
    if step:
        query = query.filter(ApplicationLogs.application_step == step)
    
    return query.order_by(ApplicationLogs.created_at.desc()).all()


def update(db: Session, log_id: int, log_in: ApplicationLogUpdate) -> Optional[ApplicationLogs]:
    """Update an application log"""
    db_log = get_by_id(db, log_id)
    if not db_log:
        return None
    
    update_data = log_in.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_log, field, value)
    
    db.commit()
    db.refresh(db_log)
    
    return db_log


def delete(db: Session, log_id: int) -> bool:
    """Delete an application log"""
    db_log = get_by_id(db, log_id)
    if not db_log:
        return False
    
    db.delete(db_log)
    db.commit()
    
    return True


def delete_bulk(db: Session, log_ids: List[int]) -> int:
    """
    Delete multiple application logs

    Args:
        db: Database session
        log_ids: List of log IDs to delete
    
    Returns:
        Number of logs deleted
    """
    try:
        deleted_count = db.query(ApplicationLogs).filter(
            ApplicationLogs.id.in_(log_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        
        return deleted_count
        
    except Exception as e:
        db.rollback()
        raise e
    
def get_last_index(db: Session, main_db_id: int) -> int:
    """
    Get the highest del_index for a specific application.
    Returns 0 if no logs exist yet.
    """
    last_index = db.query(
        func.max(ApplicationLogs.del_index)
    ).filter(
        ApplicationLogs.main_db_id == main_db_id
    ).scalar()

    return last_index or 0