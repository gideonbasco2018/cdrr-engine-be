"""
CRUD Operations for Main DB
Database operations for pharmaceutical reports
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from typing import Optional, List
from datetime import datetime, timedelta

from app.models.main_db import MainDB
from app.schemas.main_db import MainDBCreate, MainDBUpdate


def get_main_db_record(db: Session, record_id: int) -> Optional[MainDB]:
    """Get a single record by ID"""
    return db.query(MainDB).filter(MainDB.DB_ID == record_id).first()


def get_main_db_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "DB_DATE_EXCEL_UPLOAD",
    sort_order: str = "desc"
) -> tuple[List[MainDB], int]:
    """
    Get list of records with filtering, searching, and pagination
    Returns: (records, total_count)
    """
    query = db.query(MainDB)
    
    # Apply filters
    if status:
        query = query.filter(MainDB.DB_APP_STATUS == status)
    
    if category:
        query = query.filter(MainDB.DB_EST_CAT == category)
    
    # Apply search (search across multiple fields)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                MainDB.DB_DTN.like(search_pattern),
                MainDB.DB_EST_LTO_COMP.like(search_pattern),
                MainDB.DB_PROD_BR_NAME.like(search_pattern),
                MainDB.DB_PROD_GEN_NAME.like(search_pattern),
                MainDB.DB_REG_NO.like(search_pattern),
                MainDB.DB_EST_CAT.like(search_pattern)
            )
        )
    
    # Get total count before pagination
    total = query.count()
    
    # Apply sorting
    if hasattr(MainDB, sort_by):
        sort_column = getattr(MainDB, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
    
    # Apply pagination
    records = query.offset(skip).limit(limit).all()
    
    return records, total


def create_main_db_record(db: Session, record: MainDBCreate) -> MainDB:
    """Create a new record"""
    db_record = MainDB(**record.model_dump(exclude_unset=True))
    db_record.DB_DATE_EXCEL_UPLOAD = datetime.now()
    
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def update_main_db_record(
    db: Session,
    record_id: int,
    record_update: MainDBUpdate
) -> Optional[MainDB]:
    """Update an existing record"""
    db_record = get_main_db_record(db, record_id)
    
    if not db_record:
        return None
    
    # Update only provided fields
    update_data = record_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_record, field, value)
    
    db.commit()
    db.refresh(db_record)
    return db_record


def delete_main_db_record(db: Session, record_id: int) -> bool:
    """Delete a record (soft delete by setting DB_TRASH)"""
    db_record = get_main_db_record(db, record_id)
    
    if not db_record:
        return False
    
    # Soft delete
    db_record.DB_TRASH = "deleted"
    db_record.DB_TRASH_DATE_ENCODED = datetime.now()
    
    db.commit()
    return True


def hard_delete_main_db_record(db: Session, record_id: int) -> bool:
    """Permanently delete a record"""
    db_record = get_main_db_record(db, record_id)
    
    if not db_record:
        return False
    
    db.delete(db_record)
    db.commit()
    return True


def get_main_db_summary(db: Session) -> dict:
    """Get summary statistics"""
    total_records = db.query(MainDB).count()
    
    # Count by status
    status_counts = db.query(
        MainDB.DB_APP_STATUS,
        func.count(MainDB.DB_ID)
    ).group_by(MainDB.DB_APP_STATUS).all()
    
    by_status = {status or "Unknown": count for status, count in status_counts}
    
    # Count by category
    category_counts = db.query(
        MainDB.DB_EST_CAT,
        func.count(MainDB.DB_ID)
    ).group_by(MainDB.DB_EST_CAT).all()
    
    by_category = {category or "Unknown": count for category, count in category_counts}
    
    # Recent uploads (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_uploads = db.query(MainDB).filter(
        MainDB.DB_DATE_EXCEL_UPLOAD >= seven_days_ago
    ).count()
    
    return {
        "total_records": total_records,
        "by_status": by_status,
        "by_category": by_category,
        "recent_uploads": recent_uploads
    }


def bulk_create_main_db_records(
    db: Session,
    records: List[MainDBCreate]
) -> List[MainDB]:
    """Bulk create records (for Excel import)"""
    db_records = []
    
    for record in records:
        db_record = MainDB(**record.model_dump(exclude_unset=True))
        db_record.DB_DATE_EXCEL_UPLOAD = datetime.now()
        db_records.append(db_record)
    
    db.add_all(db_records)
    db.commit()
    
    # Refresh all records
    for record in db_records:
        db.refresh(record)
    
    return db_records


def get_unique_values(db: Session, field: str) -> List[str]:
    """Get unique values for a field (for filter dropdowns)"""
    if not hasattr(MainDB, field):
        return []
    
    column = getattr(MainDB, field)
    results = db.query(column).distinct().filter(column.isnot(None)).all()
    
    return [result[0] for result in results if result[0]]
