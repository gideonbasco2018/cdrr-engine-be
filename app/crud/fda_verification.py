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
                    registration_number, generic_name, brand_name, dosage_strength,
                    dosage_form, classification, packaging, pharmacologic_category,
                    manufacturer, country, trader, importer, distributor, app_type,
                    issuance_date, expiry_date, uploaded_by
                ) VALUES (
                    :registration_number, :generic_name, :brand_name, :dosage_strength,
                    :dosage_form, :classification, :packaging, :pharmacologic_category,
                    :manufacturer, :country, :trader, :importer, :distributor, :app_type,
                    :issuance_date, :expiry_date, :uploaded_by
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
                            registration_number, generic_name, brand_name, dosage_strength,
                            dosage_form, classification, packaging, pharmacologic_category,
                            manufacturer, country, trader, importer, distributor, app_type,
                            issuance_date, expiry_date, uploaded_by
                        ) VALUES (
                            :registration_number, :generic_name, :brand_name, :dosage_strength,
                            :dosage_form, :classification, :packaging, :pharmacologic_category,
                            :manufacturer, :country, :trader, :importer, :distributor, :app_type,
                            :issuance_date, :expiry_date, :uploaded_by
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


# ==================== READ ====================
def get_all_drugs(
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    include_deleted: bool = False
) -> Dict[str, Any]:
    """
    Get all drug registrations with pagination and search
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Build WHERE clause
            where_conditions = []
            params = {}
            
            if not include_deleted:
                where_conditions.append("date_deleted IS NULL")
            
            if search:
                where_conditions.append("""
                    (registration_number LIKE :search 
                    OR generic_name LIKE :search 
                    OR brand_name LIKE :search)
                """)
                params['search'] = f"%{search}%"
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Get total count
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM fda_drug_registrations
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
                SELECT *
                FROM fda_drug_registrations
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            
            result = connection.execute(data_query, params)
            
            drugs = []
            for row in result:
                drugs.append({
                    'id': row[0],
                    'registration_number': row[1],
                    'generic_name': row[2],
                    'brand_name': row[3],
                    'dosage_strength': row[4],
                    'dosage_form': row[5],
                    'classification': row[6],
                    'packaging': row[7],
                    'pharmacologic_category': row[8],
                    'manufacturer': row[9],
                    'country': row[10],
                    'trader': row[11],
                    'importer': row[12],
                    'distributor': row[13],
                    'app_type': row[14],
                    'issuance_date': row[15].isoformat() if row[15] else None,
                    'expiry_date': row[16].isoformat() if row[16] else None,
                    'uploaded_by': row[17],
                    'date_uploaded': row[18].isoformat() if row[18] else None,
                    'date_deleted': row[19].isoformat() if row[19] else None,
                    'created_at': row[20].isoformat() if row[20] else None,
                    'updated_at': row[21].isoformat() if row[21] else None,
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
                SELECT *
                FROM fda_drug_registrations
                WHERE id = :drug_id AND date_deleted IS NULL
            """)
            
            result = connection.execute(query, {'drug_id': drug_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row[0],
                'registration_number': row[1],
                'generic_name': row[2],
                'brand_name': row[3],
                'dosage_strength': row[4],
                'dosage_form': row[5],
                'classification': row[6],
                'packaging': row[7],
                'pharmacologic_category': row[8],
                'manufacturer': row[9],
                'country': row[10],
                'trader': row[11],
                'importer': row[12],
                'distributor': row[13],
                'app_type': row[14],
                'issuance_date': row[15].isoformat() if row[15] else None,
                'expiry_date': row[16].isoformat() if row[16] else None,
                'uploaded_by': row[17],
                'date_uploaded': row[18].isoformat() if row[18] else None,
                'date_deleted': row[19].isoformat() if row[19] else None,
                'created_at': row[20].isoformat() if row[20] else None,
                'updated_at': row[21].isoformat() if row[21] else None,
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
                SELECT *
                FROM fda_drug_registrations
                WHERE registration_number = :registration_number 
                AND date_deleted IS NULL
            """)
            
            result = connection.execute(query, {'registration_number': registration_number})
            row = result.fetchone()
            
            if not row:
                return {
                    "found": False,
                    "is_valid": False,
                    "data": None
                }
            
            # Check if expired
            expiry_date = row[16]
            is_expired = False
            if expiry_date and expiry_date < datetime.now().date():
                is_expired = True
            
            drug = {
                'id': row[0],
                'registration_number': row[1],
                'generic_name': row[2],
                'brand_name': row[3],
                'dosage_strength': row[4],
                'dosage_form': row[5],
                'classification': row[6],
                'manufacturer': row[9],
                'country': row[10],
                'expiry_date': row[16].isoformat() if row[16] else None,
                'is_expired': is_expired
            }
            
            return {
                "found": True,
                "is_valid": not is_expired,
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
                WHERE id = :drug_id AND date_deleted IS NULL
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


# ==================== DELETE ====================
def delete_drug(drug_id: int) -> Dict[str, Any]:
    """
    Soft delete a drug registration
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Check if exists
            check_query = text("""
                SELECT id FROM fda_drug_registrations
                WHERE id = :drug_id AND date_deleted IS NULL
            """)
            result = connection.execute(check_query, {'drug_id': drug_id})
            
            if not result.fetchone():
                return {"success": False, "error": "Drug not found"}
            
            # Soft delete
            delete_query = text("""
                UPDATE fda_drug_registrations
                SET date_deleted = NOW()
                WHERE id = :drug_id
            """)
            connection.execute(delete_query, {'drug_id': drug_id})
            connection.commit()
            
            return {"success": True, "message": "Drug deleted successfully"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
        
    finally:
        engine.dispose()