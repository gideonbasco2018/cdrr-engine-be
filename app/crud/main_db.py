"""
CRUD Operations for Main DB
Database operations for pharmaceutical reports
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_, text
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.schemas.main_db import MainDBCreate, MainDBUpdate

# -----------------------------
# Single Record
# -----------------------------
def get_main_db_record(db: Session, record_id: int) -> Optional[MainDB]:
    """Get a single record by ID with application delegation"""
    return db.query(MainDB).options(
        joinedload(MainDB.application_delegation)
    ).filter(MainDB.DB_ID == record_id).first()


# -----------------------------
# List Records with Filters/Search/Pagination
# -----------------------------
def get_main_db_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "DB_DATE_EXCEL_UPLOAD",
    sort_order: str = "desc"
) -> Tuple[List[MainDB], int]:
    """Fetch MainDB records with ApplicationDelegation (1-to-1)"""
    query = db.query(MainDB).options(joinedload(MainDB.application_delegation))

    if status:
        query = query.filter(MainDB.DB_APP_STATUS == status)

    if category:
        query = query.filter(MainDB.DB_EST_CAT == category)

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

    total = query.count()

    if hasattr(MainDB, sort_by):
        sort_column = getattr(MainDB, sort_by)
        query = query.order_by(desc(sort_column) if sort_order.lower() == "desc" else sort_column)

    records = query.offset(skip).limit(limit).all()
    return records, total


# -----------------------------
# Application Logs per MainDB Record
# -----------------------------
def get_application_logs(
    db: Session,
    main_id: int,
    skip: int = 0,
    limit: int = 50
) -> Tuple[List[ApplicationLogs], int]:
    """Fetch paginated logs for a specific MainDB record"""
    query = db.query(ApplicationLogs).filter(ApplicationLogs.main_db_id == main_id)
    total = query.count()
    logs = query.order_by(ApplicationLogs.created_at.desc()).offset(skip).limit(limit).all()
    return logs, total


# -----------------------------
# Create / Update
# -----------------------------
def create_main_db_record(db: Session, record: MainDBCreate) -> MainDB:
    """Create a new record with proper type handling"""
    data = record.model_dump(exclude_unset=True)
    # Handle datetime fields - convert string to datetime if needed
    if 'DB_DATE_EXCEL_UPLOAD' not in data or data['DB_DATE_EXCEL_UPLOAD'] is None:
        data['DB_DATE_EXCEL_UPLOAD'] = datetime.now()
    elif isinstance(data.get('DB_DATE_EXCEL_UPLOAD'), str):
        try:
            data['DB_DATE_EXCEL_UPLOAD'] = datetime.strptime(data['DB_DATE_EXCEL_UPLOAD'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            data['DB_DATE_EXCEL_UPLOAD'] = datetime.now()
    
    # Handle trash date if present
    if data.get('DB_TRASH_DATE_ENCODED') and isinstance(data['DB_TRASH_DATE_ENCODED'], str):
        try:
            data['DB_TRASH_DATE_ENCODED'] = datetime.strptime(data['DB_TRASH_DATE_ENCODED'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            data['DB_TRASH_DATE_ENCODED'] = None
    
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

    update_data = record_update.model_dump(exclude_unset=True)
    
    # Handle datetime conversions if needed
    if update_data.get('DB_DATE_EXCEL_UPLOAD') and isinstance(update_data['DB_DATE_EXCEL_UPLOAD'], str):
        try:
            update_data['DB_DATE_EXCEL_UPLOAD'] = datetime.strptime(update_data['DB_DATE_EXCEL_UPLOAD'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    
    if update_data.get('DB_TRASH_DATE_ENCODED') and isinstance(update_data['DB_TRASH_DATE_ENCODED'], str):
        try:
            update_data['DB_TRASH_DATE_ENCODED'] = datetime.strptime(update_data['DB_TRASH_DATE_ENCODED'], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    
    for field, value in update_data.items():
        setattr(db_record, field, value)

    db.commit()
    db.refresh(db_record)
    return db_record


# -----------------------------
# Delete (Soft / Hard)
# -----------------------------
def delete_main_db_record(db: Session, record_id: int) -> bool:
    """Soft delete a record"""
    db_record = get_main_db_record(db, record_id)
    if not db_record:
        return False
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


# -----------------------------
# Bulk Operations
# -----------------------------
def bulk_create_main_db_records(db: Session, records: List[MainDBCreate]) -> List[MainDB]:
    """Bulk create MainDB records"""
    db_records = []
    for record in records:
        data = record.model_dump(exclude_unset=True)
        if 'DB_DATE_EXCEL_UPLOAD' not in data:
            data['DB_DATE_EXCEL_UPLOAD'] = datetime.now()
        db_records.append(MainDB(**data))
    db.add_all(db_records)
    db.commit()
    for record in db_records:
        db.refresh(record)
    return db_records


def bulk_delete_main_db_records(db: Session, record_ids: List[int]) -> int:
    """
    Soft delete multiple records from main_db table

    Args:
        db: Database session
        record_ids: List of record IDs to delete

    Returns:
        int: Number of records deleted
    """
    if not record_ids:
        return 0
    try:
        deleted_count = db.query(MainDB).filter(MainDB.DB_ID.in_(record_ids)).update(
            {"DB_TRASH": "deleted", "DB_TRASH_DATE_ENCODED": datetime.now()},
            synchronize_session=False
        )
        db.commit()
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"Error bulk deleting records: {e}")
        return 0


# -----------------------------
# Summary / Statistics
# -----------------------------
def get_main_db_summary(db: Session) -> dict:
    """Summary statistics"""
    total_records = db.query(MainDB).count()
    status_counts = db.query(MainDB.DB_APP_STATUS, func.count(MainDB.DB_ID)).group_by(MainDB.DB_APP_STATUS).all()
    category_counts = db.query(MainDB.DB_EST_CAT, func.count(MainDB.DB_ID)).group_by(MainDB.DB_EST_CAT).all()
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_uploads = db.query(MainDB).filter(MainDB.DB_DATE_EXCEL_UPLOAD >= seven_days_ago).count()

    return {
        "total_records": total_records,
        "by_status": {status or "Unknown": count for status, count in status_counts},
        "by_category": {category or "Unknown": count for category, count in category_counts},
        "recent_uploads": recent_uploads
    }


def get_upload_statistics(db: Session) -> dict:
    """Detailed upload statistics"""
    try:
        total = db.query(MainDB).count()
        status_counts = db.query(MainDB.DB_APP_STATUS, func.count(MainDB.DB_ID)).group_by(MainDB.DB_APP_STATUS).all()
        category_counts = db.query(MainDB.DB_EST_CAT, func.count(MainDB.DB_ID)).group_by(MainDB.DB_EST_CAT)\
            .order_by(desc(func.count(MainDB.DB_ID))).limit(10).all()
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_uploads_query = db.query(
            func.date(MainDB.DB_DATE_EXCEL_UPLOAD).label('date'),
            func.count(MainDB.DB_ID).label('count')
        ).filter(MainDB.DB_DATE_EXCEL_UPLOAD >= seven_days_ago)\
            .group_by(func.date(MainDB.DB_DATE_EXCEL_UPLOAD))\
            .order_by(desc(func.date(MainDB.DB_DATE_EXCEL_UPLOAD))).all()

        recent_uploads = [{"date": str(row[0]) if row[0] else None, "count": row[1]} for row in recent_uploads_query]

        return {
            "total": total,
            "by_status": {status or "Unknown": count for status, count in status_counts},
            "by_category": {category or "Unknown": count for category, count in category_counts},
            "recent_uploads": recent_uploads
        }
    except Exception as e:
        print(f"Error getting upload statistics: {e}")
        return {"total": 0, "by_status": {}, "by_category": {}, "recent_uploads": []}


# -----------------------------
# Utilities
# -----------------------------
def get_unique_values(db: Session, field: str) -> List[str]:
    """Get distinct values for a field"""
    if not hasattr(MainDB, field):
        return []
    column = getattr(MainDB, field)
    results = db.query(column).distinct().filter(column.isnot(None)).all()
    return [r[0] for r in results if r[0]]


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
        # Using raw SQL for better performance
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
            {"uploader": row[0] or "Unknown", "upload_date": str(row[1]) if row[1] else None, "record_count": row[2]}
            for row in rows
        ]
        return history

    except Exception as e:
        print(f"Error fetching upload history: {e}")
        # Fallback to ORM query
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
                desc(func.date(MainDB.DB_DATE_EXCEL_UPLOAD))
            ).limit(limit).all()

            return [
                {"uploader": row[0] or "Unknown", "upload_date": str(row[1]) if row[1] else None, "record_count": row[2]}
                for row in results
            ]
        except Exception as e2:
            print(f"Fallback query failed: {e2}")
            return []