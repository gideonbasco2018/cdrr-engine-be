from sqlalchemy import text, or_
from sqlalchemy.orm import Session
from typing import Optional


def create_otc_record(db: Session, record_data: dict) -> dict:
    """Insert a single OTC record using raw SQL. Returns the inserted row with DB_ID."""

    columns = ", ".join(f"`{k}`" for k in record_data.keys())
    placeholders = ", ".join(f":{k}" for k in record_data.keys())

    sql = text(f"INSERT INTO main_db ({columns}) VALUES ({placeholders})")
    result = db.execute(sql, record_data)
    db.commit()

    return {"DB_ID": result.lastrowid, **record_data}


def bulk_create_otc_records(db: Session, records: list[dict]) -> int:
    """Bulk insert OTC records. Returns count of inserted rows."""
    if not records:
        return 0

    inserted = 0
    for record_data in records:
        columns = ", ".join(f"`{k}`" for k in record_data.keys())
        placeholders = ", ".join(f":{k}" for k in record_data.keys())
        sql = text(f"INSERT INTO main_db ({columns}) VALUES ({placeholders})")
        db.execute(sql, record_data)
        inserted += 1

    db.commit()
    return inserted


def get_otc_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    prescription: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    lto_company: Optional[str] = None,
    registration_no: Optional[str] = None,
    app_type: Optional[str] = None,
    is_in_pm: Optional[str] = None,  # ✅ CHANGED: from decking_status to is_in_pm
    sort_by: Optional[str] = "DB_DATE_EXCEL_UPLOAD",
    sort_order: Optional[str] = "desc"
) -> dict:
    """
    Get OTC records with pagination and comprehensive filtering.
    
    Args:
        skip: Number of records to skip (pagination offset)
        limit: Maximum number of records to return
        search: General search term (searches across brand name, generic name, registration no)
        app_status: Filter by application status (TO_DO, IN_PROGRESS, COMPLETED, etc.)
        prescription: Filter by prescription type
        brand_name: Filter by brand name (partial match)
        generic_name: Filter by generic name (partial match)
        lto_company: Filter by LTO company (partial match)
        registration_no: Filter by registration number (partial match)
        app_type: Filter by application type
        is_in_pm: Filter by PM status - 'not_in_pm' (blank/N/A) or 'in_pm' (value=1)
        sort_by: Column to sort by (default: DB_DATE_EXCEL_UPLOAD)
        sort_order: Sort order - 'asc' or 'desc' (default: desc)
    
    Returns:
        dict with total count, records, skip, and limit
    """
    
    # Base query
    where_clauses = []
    params = {"skip": skip, "limit": limit}
    
    # General search filter (searches across multiple columns)
    if search:
        where_clauses.append(
            "(DB_PROD_BR_NAME LIKE :search OR "
            "DB_PROD_GEN_NAME LIKE :search OR "
            "DB_REG_NO LIKE :search OR "
            "DB_EST_LTO_COMP LIKE :search OR "
            "DB_DTN LIKE :search)"
        )
        params["search"] = f"%{search}%"
    
    # Specific field filters
    if app_status:
        where_clauses.append("DB_APP_STATUS = :app_status")
        params["app_status"] = app_status
    
    if prescription:
        where_clauses.append("DB_PROD_CLASS_PRESCRIP = :prescription")
        params["prescription"] = prescription
    
    if brand_name:
        where_clauses.append("DB_PROD_BR_NAME LIKE :brand_name")
        params["brand_name"] = f"%{brand_name}%"
    
    if generic_name:
        where_clauses.append("DB_PROD_GEN_NAME LIKE :generic_name")
        params["generic_name"] = f"%{generic_name}%"
    
    if lto_company:
        where_clauses.append("DB_EST_LTO_COMP LIKE :lto_company")
        params["lto_company"] = f"%{lto_company}%"
    
    if registration_no:
        where_clauses.append("DB_REG_NO LIKE :registration_no")
        params["registration_no"] = f"%{registration_no}%"
    
    if app_type:
        where_clauses.append("DB_APP_TYPE = :app_type")
        params["app_type"] = app_type
    
    # ✅ NEW: is_in_pm filter (replaces decking_status)
    if is_in_pm == "not_in_pm":
        # Show records where DB_IS_IN_PM is NULL, empty, 0, or 'N/A'
        where_clauses.append(
            "(DB_IS_IN_PM IS NULL OR "
            "DB_IS_IN_PM = '' OR "
            "DB_IS_IN_PM = 'N/A' OR "
            "DB_IS_IN_PM = 'n/a' OR "
            "DB_IS_IN_PM = 0)"
        )
    elif is_in_pm == "in_pm":
        # Show records where DB_IS_IN_PM = 1 (or '1' as string)
        where_clauses.append("(DB_IS_IN_PM = 1 OR DB_IS_IN_PM = '1')")
    
    # Build WHERE clause
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    
    # Validate and sanitize sort parameters
    allowed_sort_columns = [
        "DB_ID", "DB_DTN", "DB_PROD_BR_NAME", "DB_PROD_GEN_NAME",
        "DB_REG_NO", "DB_APP_TYPE", "DB_APP_STATUS", "DB_DATE_EXCEL_UPLOAD",
        "DB_DATE_RECEIVED_FDAC", "DB_DATE_DECK", "DB_EST_LTO_COMP"
    ]
    
    if sort_by not in allowed_sort_columns:
        sort_by = "DB_DATE_EXCEL_UPLOAD"
    
    sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
    
    # Count total records
    count_sql = text(f"SELECT COUNT(*) as total FROM main_db {where_sql}")
    total = db.execute(count_sql, params).scalar()
    
    # Get records with sorting
    query_sql = text(f"""
        SELECT * FROM main_db 
        {where_sql}
        ORDER BY `{sort_by}` {sort_order}
        LIMIT :limit OFFSET :skip
    """)
    
    result = db.execute(query_sql, params)
    records = [dict(row._mapping) for row in result]
    
    return {
        "total": total,
        "records": records,
        "skip": skip,
        "limit": limit
    }


def get_otc_record_by_id(db: Session, record_id: int) -> Optional[dict]:
    """Get a single OTC record by ID."""
    sql = text("SELECT * FROM main_db WHERE DB_ID = :id")
    result = db.execute(sql, {"id": record_id}).fetchone()
    
    if result:
        return dict(result._mapping)
    return None


def update_otc_record(db: Session, record_id: int, update_data: dict) -> Optional[dict]:
    """
    Update an OTC record by ID.
    
    Args:
        record_id: The DB_ID of the record to update
        update_data: Dictionary of fields to update
    
    Returns:
        Updated record dict or None if not found
    """
    if not update_data:
        return get_otc_record_by_id(db, record_id)
    
    # Build SET clause
    set_clauses = [f"`{k}` = :{k}" for k in update_data.keys()]
    set_sql = ", ".join(set_clauses)
    
    # Add record_id to params
    params = {**update_data, "record_id": record_id}
    
    # Execute update
    sql = text(f"UPDATE main_db SET {set_sql} WHERE DB_ID = :record_id")
    result = db.execute(sql, params)
    db.commit()
    
    # Return updated record if any rows were affected
    if result.rowcount > 0:
        return get_otc_record_by_id(db, record_id)
    return None


def delete_otc_record(db: Session, record_id: int) -> bool:
    """
    Delete an OTC record by ID.
    
    Args:
        record_id: The DB_ID of the record to delete
    
    Returns:
        True if deleted, False if not found
    """
    sql = text("DELETE FROM main_db WHERE DB_ID = :id")
    result = db.execute(sql, {"id": record_id})
    db.commit()
    
    return result.rowcount > 0

def get_app_statuses(
    db: Session,
    is_in_pm: Optional[str] = None,
    app_type: Optional[str] = None,
    prescription: Optional[str] = None,
) -> list[dict]:
    where_clauses = ["DB_APP_STATUS IS NOT NULL AND DB_APP_STATUS != ''"]
    params = {}

    if is_in_pm == "not_in_pm":
        where_clauses.append(
            "(DB_IS_IN_PM IS NULL OR DB_IS_IN_PM = '' OR "
            "DB_IS_IN_PM = 'N/A' OR DB_IS_IN_PM = 'n/a' OR DB_IS_IN_PM = 0)"
        )
    elif is_in_pm == "in_pm":
        where_clauses.append("(DB_IS_IN_PM = 1 OR DB_IS_IN_PM = '1')")

    if app_type:
        where_clauses.append("DB_APP_TYPE = :app_type")
        params["app_type"] = app_type

    if prescription:
        where_clauses.append("DB_PROD_CLASS_PRESCRIP = :prescription")
        params["prescription"] = prescription

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    sql = text(f"""
        SELECT DB_APP_STATUS as value, COUNT(*) as count
        FROM main_db
        {where_sql}
        GROUP BY DB_APP_STATUS
        ORDER BY count DESC
    """)

    result = db.execute(sql, params)
    return [{"value": row.value, "count": row.count} for row in result]


def get_app_types(
    db: Session,
    is_in_pm: Optional[str] = None,
    prescription: Optional[str] = None,
    app_status: Optional[str] = None,
) -> list[dict]:
    where_clauses = ["DB_APP_TYPE IS NOT NULL AND DB_APP_TYPE != ''"]
    params = {}

    if is_in_pm == "not_in_pm":
        where_clauses.append(
            "(DB_IS_IN_PM IS NULL OR DB_IS_IN_PM = '' OR "
            "DB_IS_IN_PM = 'N/A' OR DB_IS_IN_PM = 'n/a' OR DB_IS_IN_PM = 0)"
        )
    elif is_in_pm == "in_pm":
        where_clauses.append("(DB_IS_IN_PM = 1 OR DB_IS_IN_PM = '1')")

    if prescription:
        where_clauses.append("DB_PROD_CLASS_PRESCRIP = :prescription")
        params["prescription"] = prescription

    if app_status:
        where_clauses.append("DB_APP_STATUS = :app_status")
        params["app_status"] = app_status

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    sql = text(f"""
        SELECT DB_APP_TYPE as value, COUNT(*) as count
        FROM main_db
        {where_sql}
        GROUP BY DB_APP_TYPE
        ORDER BY count DESC
    """)

    result = db.execute(sql, params)
    return [{"value": row.value, "count": row.count} for row in result]


def get_prescription_types(
    db: Session,
    is_in_pm: Optional[str] = None,
    app_type: Optional[str] = None,
    app_status: Optional[str] = None,
) -> list[dict]:
    where_clauses = ["DB_PROD_CLASS_PRESCRIP IS NOT NULL AND DB_PROD_CLASS_PRESCRIP != ''"]
    params = {}

    if is_in_pm == "not_in_pm":
        where_clauses.append(
            "(DB_IS_IN_PM IS NULL OR DB_IS_IN_PM = '' OR "
            "DB_IS_IN_PM = 'N/A' OR DB_IS_IN_PM = 'n/a' OR DB_IS_IN_PM = 0)"
        )
    elif is_in_pm == "in_pm":
        where_clauses.append("(DB_IS_IN_PM = 1 OR DB_IS_IN_PM = '1')")

    if app_type:
        where_clauses.append("DB_APP_TYPE = :app_type")
        params["app_type"] = app_type

    if app_status:
        where_clauses.append("DB_APP_STATUS = :app_status")
        params["app_status"] = app_status

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    sql = text(f"""
        SELECT DB_PROD_CLASS_PRESCRIP as value, COUNT(*) as count
        FROM main_db
        {where_sql}
        GROUP BY DB_PROD_CLASS_PRESCRIP
        ORDER BY count DESC
    """)

    result = db.execute(sql, params)
    return [{"value": row.value, "count": row.count} for row in result]

def export_otc_records_data(
    db: Session,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    prescription: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    lto_company: Optional[str] = None,
    registration_no: Optional[str] = None,
    app_type: Optional[str] = None,
    is_in_pm: Optional[str] = None,  # ✅ CHANGED: from decking_status to is_in_pm
) -> list[dict]:
    """
    Export OTC records based on filters (no pagination - returns all matching records).
    
    Returns:
        List of all matching records
    """
    # Reuse the same filtering logic from get_otc_records
    where_clauses = []
    params = {}
    
    if search:
        where_clauses.append(
            "(DB_PROD_BR_NAME LIKE :search OR "
            "DB_PROD_GEN_NAME LIKE :search OR "
            "DB_REG_NO LIKE :search OR "
            "DB_EST_LTO_COMP LIKE :search OR "
            "DB_DTN LIKE :search)"
        )
        params["search"] = f"%{search}%"
    
    if app_status:
        where_clauses.append("DB_APP_STATUS = :app_status")
        params["app_status"] = app_status
    
    if prescription:
        where_clauses.append("DB_PROD_CLASS_PRESCRIP = :prescription")
        params["prescription"] = prescription
    
    if brand_name:
        where_clauses.append("DB_PROD_BR_NAME LIKE :brand_name")
        params["brand_name"] = f"%{brand_name}%"
    
    if generic_name:
        where_clauses.append("DB_PROD_GEN_NAME LIKE :generic_name")
        params["generic_name"] = f"%{generic_name}%"
    
    if lto_company:
        where_clauses.append("DB_EST_LTO_COMP LIKE :lto_company")
        params["lto_company"] = f"%{lto_company}%"
    
    if registration_no:
        where_clauses.append("DB_REG_NO LIKE :registration_no")
        params["registration_no"] = f"%{registration_no}%"
    
    if app_type:
        where_clauses.append("DB_APP_TYPE = :app_type")
        params["app_type"] = app_type
    
    # ✅ NEW: is_in_pm filter (replaces decking_status)
    if is_in_pm == "not_in_pm":
        where_clauses.append(
            "(DB_IS_IN_PM IS NULL OR "
            "DB_IS_IN_PM = '' OR "
            "DB_IS_IN_PM = 'N/A' OR "
            "DB_IS_IN_PM = 'n/a' OR "
            "DB_IS_IN_PM = 0)"
        )
    elif is_in_pm == "in_pm":
        where_clauses.append("(DB_IS_IN_PM = 1 OR DB_IS_IN_PM = '1')")
    
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    
    # Get all records (no LIMIT)
    query_sql = text(f"""
        SELECT * FROM main_db 
        {where_sql}
        ORDER BY DB_DATE_EXCEL_UPLOAD DESC
    """)
    
    result = db.execute(query_sql, params)
    records = [dict(row._mapping) for row in result]
    
    return records