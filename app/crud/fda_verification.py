# app/crud/fda_verification.py
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Get the FDA eServices database URL from environment
REMOTE_FDA_ESERVICES_URL = os.getenv("REMOTE_FDA_ESERVICES_URL")


def get_fda_db_engine():
    """Get FDA database engine"""
    if not REMOTE_FDA_ESERVICES_URL:
        raise ValueError("REMOTE_FDA_ESERVICES_URL not configured")
    return create_engine(
        REMOTE_FDA_ESERVICES_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )


# ==================== CREATE ====================
def create_drug(drug_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new drug registration into database
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            query = text("""
                INSERT INTO fda_drug_registrations (
                    reference_number, registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, packaging, pharmacologic_category,
                    manufacturer, country_of_origin, trader, importer, distributor, app_type,
                    issuance_date, expiry_date, uploaded_by, date_uploaded
                ) VALUES (
                    :reference_number, :registration_number, :generic_name, :brand_name, :dosage_strength,
                    :dosage_form, :classification, :packaging, :pharmacologic_category,
                    :manufacturer, :country_of_origin, :trader, :importer, :distributor, :app_type,
                    :issuance_date, :expiry_date, :uploaded_by, NOW()
                )
            """)
            
            connection.execute(query, drug_data)
            connection.commit()
            
            return {"success": True, "message": "Drug created successfully"}
            
    except IntegrityError as e:
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if 'Duplicate entry' in error_msg:
            return {"success": False, "error": "Duplicate registration number"}
        return {"success": False, "error": error_msg}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        engine.dispose()


def bulk_create_drugs(drugs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Bulk insert drug registrations
    Returns: {successful: int, failed: int, errors: List}
    """
    engine = get_fda_db_engine()
    successful = 0
    failed = 0
    errors = []
    
    try:
        with engine.connect() as connection:
            for idx, drug_data in enumerate(drugs_data):
                try:
                    query = text("""
                        INSERT INTO fda_drug_registrations (
                            reference_number, registration_number, generic_name, brand_name, dosage_strength,
                            dosage_form, classification, packaging, pharmacologic_category,
                            manufacturer, country_of_origin, trader, importer, distributor, app_type,
                            issuance_date, expiry_date, uploaded_by, date_uploaded
                        ) VALUES (
                            :reference_number, :registration_number, :generic_name, :brand_name, :dosage_strength,
                            :dosage_form, :classification, :packaging, :pharmacologic_category,
                            :manufacturer, :country_of_origin, :trader, :importer, :distributor, :app_type,
                            :issuance_date, :expiry_date, :uploaded_by, NOW()
                        )
                    """)
                    
                    connection.execute(query, drug_data)
                    connection.commit()
                    successful += 1
                    
                except IntegrityError as e:
                    failed += 1
                    error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
                    if 'Duplicate entry' in error_msg:
                        errors.append({
                            'row': idx + 2,
                            'registration_number': drug_data.get('registration_number'),
                            'error': 'Duplicate registration number'
                        })
                    else:
                        errors.append({
                            'row': idx + 2,
                            'registration_number': drug_data.get('registration_number'),
                            'error': error_msg
                        })
                    connection.rollback()
                    
                except Exception as e:
                    failed += 1
                    errors.append({
                        'row': idx + 2,
                        'registration_number': drug_data.get('registration_number', 'N/A'),
                        'error': str(e)
                    })
                    connection.rollback()
        
        return {
            "successful": successful,
            "failed": failed,
            "errors": errors[:10]
        }
        
    finally:
        engine.dispose()


def get_all_drugs(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    include_canceled: bool = False,
    expired_only: bool = False,
    duplicates_only: bool = False,
    uploaded_today: bool = False,
    uploaded_yesterday: bool = False,
    uploaded_this_month: bool = False,
    uploaded_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get all drug registrations with pagination and search
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            where_conditions = []
            params = {}

            if duplicates_only:
                # ✅ duplicates_only handles its own filtering
                where_conditions.append("""
                    (is_canceled IS NULL OR is_canceled = 'N')
                    AND registration_number IS NOT NULL
                    AND registration_number != ''
                    AND registration_number IN (
                        SELECT registration_number
                        FROM cdrr_manual.fda_drug_registrations
                        WHERE (is_canceled IS NULL OR is_canceled = 'N')
                          AND registration_number IS NOT NULL
                          AND registration_number != ''
                        GROUP BY registration_number
                        HAVING COUNT(*) >= 2
                    )
                """)
            else:
                if not include_canceled:
                    where_conditions.append("(is_canceled IS NULL OR is_canceled = 'N')")

                if expired_only:
                    where_conditions.append("expiry_date < CURDATE()")

                if uploaded_today:
                    where_conditions.append("DATE(date_uploaded) = CURDATE()")

                if uploaded_yesterday:
                    where_conditions.append("DATE(date_uploaded) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)")

                if uploaded_this_month:
                    where_conditions.append("""
                        MONTH(date_uploaded) = MONTH(CURDATE())
                        AND YEAR(date_uploaded) = YEAR(CURDATE())
                    """)

            # ✅ These apply to ALL tabs including duplicates
            if uploaded_by:
                where_conditions.append("uploaded_by = :uploaded_by")
                params['uploaded_by'] = uploaded_by

            if search:
                where_conditions.append("""
                    (registration_number LIKE :search 
                    OR reference_number LIKE :search
                    OR generic_name LIKE :search 
                    OR brand_name LIKE :search)
                """)
                params['search'] = f"%{search}%"

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            # Get total count
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM cdrr_manual.fda_drug_registrations
                WHERE {where_clause}
            """)
            total_result = connection.execute(count_query, params)
            total = total_result.fetchone()[0]

            # Calculate offset
            offset = (page - 1) * page_size

            # Get paginated data
            params['limit'] = page_size
            params['offset'] = offset

            data_query = text(f"""
                SELECT 
                    id, reference_number, registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, packaging, pharmacologic_category,
                    manufacturer, country_of_origin, trader, importer, distributor,
                    app_type, issuance_date, expiry_date, uploaded_by, date_uploaded,
                    is_canceled, canceled_by, date_canceled, date_modified
                FROM cdrr_manual.fda_drug_registrations
                WHERE {where_clause}
                ORDER BY date_modified DESC, id DESC
                LIMIT :limit OFFSET :offset
            """)

            result = connection.execute(data_query, params)

            drugs = []
            for row in result:
                drugs.append({
                    'id': row[0],
                    'reference_number': row[1],
                    'registration_number': row[2],
                    'generic_name': row[3],
                    'brand_name': row[4],
                    'dosage_strength': row[5],
                    'dosage_form': row[6],
                    'classification': row[7],
                    'packaging': row[8],
                    'pharmacologic_category': row[9],
                    'manufacturer': row[10],
                    'country_of_origin': row[11],
                    'trader': row[12],
                    'importer': row[13],
                    'distributor': row[14],
                    'app_type': row[15],
                    'issuance_date': row[16].isoformat() if row[16] else None,
                    'expiry_date': row[17].isoformat() if row[17] else None,
                    'uploaded_by': row[18],
                    'date_uploaded': row[19].isoformat() if row[19] else None,
                    'is_canceled': row[20] if row[20] else 'N',
                    'canceled_by': row[21],
                    'date_canceled': row[22].isoformat() if row[22] else None,
                    'date_modified': row[23].isoformat() if row[23] else None,
                })

            total_pages = (total + page_size - 1) // page_size

            return {
                "drugs": drugs,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }

    finally:
        engine.dispose()


def get_drug_by_id(drug_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific drug registration by ID
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    id, reference_number, registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, packaging, pharmacologic_category,
                    manufacturer, country_of_origin, trader, importer, distributor,
                    app_type, issuance_date, expiry_date, uploaded_by, date_uploaded,
                    is_canceled, canceled_by, date_canceled, date_modified
                FROM fda_drug_registrations
                WHERE id = :drug_id AND (is_canceled IS NULL OR is_canceled = 'N')
            """)
            
            result = connection.execute(query, {'drug_id': drug_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row[0],
                'reference_number': row[1],
                'registration_number': row[2],
                'generic_name': row[3],
                'brand_name': row[4],
                'dosage_strength': row[5],
                'dosage_form': row[6],
                'classification': row[7],
                'packaging': row[8],
                'pharmacologic_category': row[9],
                'manufacturer': row[10],
                'country_of_origin': row[11],
                'trader': row[12],
                'importer': row[13],
                'distributor': row[14],
                'app_type': row[15],
                'issuance_date': row[16].isoformat() if row[16] else None,
                'expiry_date': row[17].isoformat() if row[17] else None,
                'uploaded_by': row[18],
                'date_uploaded': row[19].isoformat() if row[19] else None,
                'is_canceled': row[20] if row[20] else 'N',
                'canceled_by': row[21],
                'date_canceled': row[22].isoformat() if row[22] else None,
                'date_modified': row[23].isoformat() if row[23] else None,
            }
        
    finally:
        engine.dispose()


def verify_registration(registration_number: str) -> Dict[str, Any]:
    """
    Verify if a registration number exists and is valid
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            query = text("""
                SELECT 
                    id, reference_number, registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, manufacturer, country_of_origin,
                    expiry_date, is_canceled
                FROM fda_drug_registrations
                WHERE registration_number = :registration_number 
                AND (is_canceled IS NULL OR is_canceled = 'N')
            """)
            
            result = connection.execute(query, {'registration_number': registration_number})
            row = result.fetchone()
            
            if not row:
                return {
                    "found": False,
                    "is_valid": False,
                    "data": None
                }
            
            # Check if expired or canceled
            expiry_date = row[10]
            is_canceled = row[11]
            
            is_expired = False
            if expiry_date and expiry_date < datetime.now().date():
                is_expired = True
            
            is_valid = not is_expired and (is_canceled is None or is_canceled == 'N')
            
            drug = {
                'id': row[0],
                'reference_number': row[1],
                'registration_number': row[2],
                'generic_name': row[3],
                'brand_name': row[4],
                'dosage_strength': row[5],
                'dosage_form': row[6],
                'classification': row[7],
                'manufacturer': row[8],
                'country_of_origin': row[9],
                'expiry_date': row[10].isoformat() if row[10] else None,
                'is_expired': is_expired,
                'is_canceled': is_canceled if is_canceled else 'N'
            }
            
            return {
                "found": True,
                "is_valid": is_valid,
                "data": drug
            }
        
    finally:
        engine.dispose()


# ==================== UPDATE ====================
def update_drug(drug_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update a drug registration
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Check if exists
            check_query = text("""
                SELECT id FROM fda_drug_registrations
                WHERE id = :drug_id AND (is_canceled IS NULL OR is_canceled = 'N')
            """)
            result = connection.execute(check_query, {'drug_id': drug_id})
            
            if not result.fetchone():
                return {"success": False, "error": "Drug not found"}
            
            # Build update query dynamically
            set_clauses = []
            params = {'drug_id': drug_id}
            
            for key, value in update_data.items():
                if value is not None:
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = value
            
            if not set_clauses:
                return {"success": False, "error": "No data to update"}
            
            # Always update date_modified
            set_clauses.append("date_modified = NOW()")
            
            update_query = text(f"""
                UPDATE fda_drug_registrations
                SET {', '.join(set_clauses)}
                WHERE id = :drug_id
            """)
            
            connection.execute(update_query, params)
            connection.commit()
            
            return {"success": True, "message": "Drug updated successfully"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        engine.dispose()


# ==================== CANCEL / RESTORE ====================
def cancel_drug(drug_id: int, canceled_by: str) -> Dict[str, Any]:
    """
    Cancel a drug registration (set is_canceled = 'Y')
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Check if exists and not already canceled
            check_query = text("""
                SELECT id, is_canceled FROM fda_drug_registrations
                WHERE id = :drug_id
            """)
            result = connection.execute(check_query, {'drug_id': drug_id})
            row = result.fetchone()
            
            if not row:
                return {"success": False, "error": "Drug not found"}
            
            if row[1] == 'Y':
                return {"success": False, "error": "Drug is already canceled"}
            
            # Cancel the drug
            cancel_query = text("""
                UPDATE fda_drug_registrations
                SET is_canceled = 'Y',
                    canceled_by = :canceled_by,
                    date_canceled = NOW(),
                    date_modified = NOW()
                WHERE id = :drug_id
            """)
            connection.execute(cancel_query, {
                'drug_id': drug_id,
                'canceled_by': canceled_by
            })
            connection.commit()
            
            return {"success": True, "message": "Drug registration canceled successfully"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        engine.dispose()


def restore_drug(drug_id: int) -> Dict[str, Any]:
    """
    Restore a canceled drug registration (set is_canceled = 'N')
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Check if exists and is canceled
            check_query = text("""
                SELECT id, is_canceled FROM fda_drug_registrations
                WHERE id = :drug_id
            """)
            result = connection.execute(check_query, {'drug_id': drug_id})
            row = result.fetchone()
            
            if not row:
                return {"success": False, "error": "Drug not found"}
            
            if row[1] != 'Y':
                return {"success": False, "error": "Drug is not canceled"}
            
            # Restore the drug
            restore_query = text("""
                UPDATE fda_drug_registrations
                SET is_canceled = 'N',
                    canceled_by = NULL,
                    date_canceled = NULL,
                    date_modified = NOW()
                WHERE id = :drug_id
            """)
            connection.execute(restore_query, {'drug_id': drug_id})
            connection.commit()
            
            return {"success": True, "message": "Drug registration restored successfully"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        engine.dispose()


# ==================== EXPORT ====================
def export_all_drugs(
    search: Optional[str] = None,
    include_canceled: bool = False
) -> Dict[str, Any]:
    """
    Get ALL drug registrations for export (no pagination limit)
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Build WHERE clause
            where_conditions = []
            params = {}
            
            if not include_canceled:
                where_conditions.append("(is_canceled IS NULL OR is_canceled = 'N')")
            
            if search:
                where_conditions.append("""
                    (registration_number LIKE :search 
                    OR reference_number LIKE :search
                    OR generic_name LIKE :search 
                    OR brand_name LIKE :search)
                """)
                params['search'] = f"%{search}%"
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Get ALL data (no LIMIT)
            data_query = text(f"""
                SELECT 
                    id, reference_number, registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, packaging, pharmacologic_category,
                    manufacturer, country_of_origin, trader, importer, distributor,
                    app_type, issuance_date, expiry_date, uploaded_by, date_uploaded,
                    is_canceled, canceled_by, date_canceled, date_modified
                FROM fda_drug_registrations
                WHERE {where_clause}
                ORDER BY date_modified DESC, id DESC
            """)
            
            result = connection.execute(data_query, params)
            
            drugs = []
            for row in result:
                drugs.append({
                    'id': row[0],
                    'reference_number': row[1],
                    'registration_number': row[2],
                    'generic_name': row[3],
                    'brand_name': row[4],
                    'dosage_strength': row[5],
                    'dosage_form': row[6],
                    'classification': row[7],
                    'packaging': row[8],
                    'pharmacologic_category': row[9],
                    'manufacturer': row[10],
                    'country_of_origin': row[11],
                    'trader': row[12],
                    'importer': row[13],
                    'distributor': row[14],
                    'app_type': row[15],
                    'issuance_date': row[16].isoformat() if row[16] else None,
                    'expiry_date': row[17].isoformat() if row[17] else None,
                    'uploaded_by': row[18],
                    'date_uploaded': row[19].isoformat() if row[19] else None,
                    'is_canceled': row[20] if row[20] else 'N',
                    'canceled_by': row[21],
                    'date_canceled': row[22].isoformat() if row[22] else None,
                    'date_modified': row[23].isoformat() if row[23] else None,
                })
            
            return {
                "drugs": drugs,
                "total": len(drugs)
            }
        
    finally:
        engine.dispose()

def bulk_create_drugs_from_dtns(
    dtn_list: List[int],
    uploaded_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Bulk insert FDA drug registrations sourced from main_db DTN records.
    Called during End Task flow — fetches each DTN from main_db (local DB),
    then inserts into fda_drug_registrations (FDA eServices DB).

    Args:
        dtn_list: List of DB_DTN values to process
        uploaded_by: Username of the user who triggered End Task

    Returns:
        {successful: int, failed: int, skipped: int, errors: List}
    """
    from app.db.session import SessionLocal  # local main_db session

    local_db = SessionLocal()
    fda_engine = get_fda_db_engine()

    successful = 0
    failed = 0
    skipped = 0
    errors = []

    try:
        # ── 1. Fetch all DTN records from main_db (local DB) ──────────────
        from app.models.main_db import MainDB

        dtn_records = (
            local_db.query(MainDB)
            .filter(MainDB.DB_DTN.in_(dtn_list))
            .all()
        )

        # Map fetched records by DTN for quick lookup
        fetched_dtns = {str(r.DB_DTN): r for r in dtn_records}

        # Report any DTNs not found in main_db
        for dtn in dtn_list:
            if str(dtn) not in fetched_dtns:
                skipped += 1
                errors.append({
                    "dtn": dtn,
                    "registration_number": None,
                    "error": "DTN not found in main_db"
                })

        # ── 2. Insert each record into fda_drug_registrations ─────────────
        with fda_engine.connect() as connection:
            for dtn_key, record in fetched_dtns.items():

                # Skip if no registration number — nothing meaningful to insert
                if not record.DB_REG_NO or not str(record.DB_REG_NO).strip():
                    skipped += 1
                    errors.append({
                        "dtn": record.DB_DTN,
                        "registration_number": None,
                        "error": "No registration number on DTN record"
                    })
                    continue

                # ── Parse issuance_date ────────────────────────────────────
                issuance_date = None
                if record.DB_DATE_ISSUED:
                    raw_issued = str(record.DB_DATE_ISSUED).strip()
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            from datetime import datetime as dt
                            issuance_date = dt.strptime(raw_issued, fmt).date()
                            break
                        except ValueError:
                            continue

                # ── Parse expiry_date (CPR Validity) ──────────────────────
                expiry_date = None
                if record.DB_CPR_VALIDITY:
                    raw_expiry = str(record.DB_CPR_VALIDITY).strip()
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            from datetime import datetime as dt
                            expiry_date = dt.strptime(raw_expiry, fmt).date()
                            break
                        except ValueError:
                            continue

                # ── Map fields ────────────────────────────────────────────
                drug_data = {
                    "reference_number":      str(record.DB_DTN) if record.DB_DTN else None,
                    "registration_number":   str(record.DB_REG_NO).strip(),
                    "generic_name":          str(record.DB_PROD_GEN_NAME).strip() if record.DB_PROD_GEN_NAME else None,
                    "brand_name":            str(record.DB_PROD_BR_NAME).strip() if record.DB_PROD_BR_NAME else None,
                    "dosage_strength":       str(record.DB_PROD_DOS_STR).strip() if record.DB_PROD_DOS_STR else None,
                    "dosage_form":           str(record.DB_PROD_DOS_FORM).strip() if record.DB_PROD_DOS_FORM else None,
                    "classification":        str(record.DB_CLASS).strip() if record.DB_CLASS else None,
                    "packaging":             str(record.DB_PACKAGING).strip() if record.DB_PACKAGING else None,
                    "pharmacologic_category":str(record.DB_PROD_PHARMA_CAT).strip() if record.DB_PROD_PHARMA_CAT else None,
                    "manufacturer":          str(record.DB_PROD_MANU).strip() if record.DB_PROD_MANU else None,
                    "country_of_origin":     str(record.DB_PROD_MANU_COUNTRY).strip() if record.DB_PROD_MANU_COUNTRY else None,
                    "trader":                str(record.DB_PROD_TRADER).strip() if record.DB_PROD_TRADER else None,
                    "importer":              str(record.DB_PROD_IMPORTER).strip() if record.DB_PROD_IMPORTER else None,
                    "distributor":           str(record.DB_PROD_DISTRI).strip() if record.DB_PROD_DISTRI else None,
                    "app_type":              str(record.DB_APP_TYPE).strip() if record.DB_APP_TYPE else None,
                    "issuance_date":         issuance_date,
                    "expiry_date":           expiry_date,
                    "uploaded_by":           uploaded_by or record.DB_USER_UPLOADER,
                }

                try:
                    insert_query = text("""
                        INSERT INTO fda_drug_registrations (
                            reference_number, registration_number, generic_name, brand_name,
                            dosage_strength, dosage_form, classification, packaging,
                            pharmacologic_category, manufacturer, country_of_origin,
                            trader, importer, distributor, app_type,
                            issuance_date, expiry_date, uploaded_by, date_uploaded
                        ) VALUES (
                            :reference_number, :registration_number, :generic_name, :brand_name,
                            :dosage_strength, :dosage_form, :classification, :packaging,
                            :pharmacologic_category, :manufacturer, :country_of_origin,
                            :trader, :importer, :distributor, :app_type,
                            :issuance_date, :expiry_date, :uploaded_by, NOW()
                        )
                    """)

                    connection.execute(insert_query, drug_data)
                    connection.commit()
                    successful += 1

                except IntegrityError as e:
                    connection.rollback()
                    failed += 1
                    error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
                    errors.append({
                        "dtn": record.DB_DTN,
                        "registration_number": drug_data["registration_number"],
                        "error": "Duplicate registration number" if "Duplicate entry" in error_msg else error_msg
                    })

                except Exception as e:
                    connection.rollback()
                    failed += 1
                    errors.append({
                        "dtn": record.DB_DTN,
                        "registration_number": drug_data.get("registration_number"),
                        "error": str(e)
                    })

        return {
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "errors": errors[:10]  # cap to first 10 errors same as existing pattern
        }

    finally:
        local_db.close()
        fda_engine.dispose()