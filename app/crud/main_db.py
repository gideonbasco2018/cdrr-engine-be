"""
CRUD Operations for Main DB
Database operations for pharmaceutical reports
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, text
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
    """Create a new record, ensure all values are strings"""
    # Convert all fields to strings (or None) before passing to SQLAlchemy
    data = {k: (str(v) if v is not None else None) for k, v in record.model_dump(exclude_unset=True).items()}

    db_record = MainDB(**data)
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


def get_upload_history(db: Session, limit: int = 50) -> List[dict]:
    """
    Get upload history grouped by user and date
    
    Args:
        db: Database session
        limit: Maximum number of records to return
        
    Returns:
        List of upload history records
    """
    try:
        # Using raw SQL for better compatibility
        query = text("""
            SELECT 
                DB_USER_UPLOADER as uploader,
                DATE(DB_DATE_EXCEL_UPLOAD) as upload_date,
                COUNT(*) as record_count
            FROM main_db
            WHERE DB_DATE_EXCEL_UPLOAD IS NOT NULL
            GROUP BY DB_USER_UPLOADER, DATE(DB_DATE_EXCEL_UPLOAD)
            ORDER BY DB_DATE_EXCEL_UPLOAD DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {"limit": limit})
        rows = result.fetchall()
        
        history = [
            {
                "uploader": row[0] or "Unknown",
                "upload_date": str(row[1]) if row[1] else None,
                "record_count": row[2]
            }
            for row in rows
        ]
        
        return history
        
    except Exception as e:
        print(f"Error fetching upload history: {e}")
        # Fallback to ORM query if raw SQL fails
        try:
            results = db.query(
                MainDB.DB_USER_UPLOADER,
                func.date(MainDB.DB_DATE_EXCEL_UPLOAD).label('upload_date'),
                func.count(MainDB.DB_ID).label('record_count')
            ).filter(
                MainDB.DB_DATE_EXCEL_UPLOAD.isnot(None)
            ).group_by(
                MainDB.DB_USER_UPLOADER,
                func.date(MainDB.DB_DATE_EXCEL_UPLOAD)
            ).order_by(
                desc(MainDB.DB_DATE_EXCEL_UPLOAD)
            ).limit(limit).all()
            
            return [
                {
                    "uploader": row[0] or "Unknown",
                    "upload_date": str(row[1]) if row[1] else None,
                    "record_count": row[2]
                }
                for row in results
            ]
        except Exception as e2:
            print(f"Fallback query also failed: {e2}")
            return []


def bulk_delete_main_db_records(db: Session, record_ids: List[int]) -> int:
    """
    Delete multiple records from main_db table
    
    Args:
        db: Database session
        record_ids: List of record IDs to delete
        
    Returns:
        int: Number of records deleted
    """
    if not record_ids:
        return 0
    
    try:
        deleted_count = db.query(MainDB).filter(
            MainDB.DB_ID.in_(record_ids)
        ).update(
            {
                "DB_TRASH": "deleted",
                "DB_TRASH_DATE_ENCODED": datetime.now()
            },
            synchronize_session=False
        )
        
        db.commit()
        return deleted_count
        
    except Exception as e:
        db.rollback()
        print(f"Error bulk deleting records: {e}")
        return 0


def get_upload_statistics(db: Session) -> dict:
    """
    Get detailed statistics about uploaded data
    
    Returns:
        dict: Statistics including total, by status, by category, etc.
    """
    try:
        # Total records
        total = db.query(MainDB).count()
        
        # By status
        status_counts = db.query(
            MainDB.DB_APP_STATUS,
            func.count(MainDB.DB_ID)
        ).group_by(MainDB.DB_APP_STATUS).all()
        
        by_status = {
            status or "Unknown": count 
            for status, count in status_counts
        }
        
        # By category (top 10)
        category_counts = db.query(
            MainDB.DB_EST_CAT,
            func.count(MainDB.DB_ID)
        ).group_by(
            MainDB.DB_EST_CAT
        ).order_by(
            desc(func.count(MainDB.DB_ID))
        ).limit(10).all()
        
        by_category = {
            category or "Unknown": count 
            for category, count in category_counts
        }
        
        # Recent uploads (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        recent_uploads_query = db.query(
            func.date(MainDB.DB_DATE_EXCEL_UPLOAD).label('date'),
            func.count(MainDB.DB_ID).label('count')
        ).filter(
            MainDB.DB_DATE_EXCEL_UPLOAD >= seven_days_ago
        ).group_by(
            func.date(MainDB.DB_DATE_EXCEL_UPLOAD)
        ).order_by(
            desc(func.date(MainDB.DB_DATE_EXCEL_UPLOAD))
        ).all()
        
        recent_uploads = [
            {
                "date": str(row[0]) if row[0] else None,
                "count": row[1]
            }
            for row in recent_uploads_query
        ]
        
        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category,
            "recent_uploads": recent_uploads
        }
        
    except Exception as e:
        print(f"Error getting upload statistics: {e}")
        return {
            "total": 0,
            "by_status": {},
            "by_category": {},
            "recent_uploads": []
        }