"""
FDA Verification Portal - Statistics CRUD
Database operations for statistics and dashboard metrics
"""
from sqlalchemy import create_engine, text
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv

load_dotenv()

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


# ==================== DASHBOARD STATISTICS ====================
def get_dashboard_statistics(uploaded_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive dashboard statistics
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            # Build WHERE clause for uploaded_by filter
            user_filter = ""
            params = {}
            
            if uploaded_by:
                user_filter = " AND uploaded_by = :uploaded_by"
                params['uploaded_by'] = uploaded_by
            
            # 1. Total Manual Application Released (all non-canceled records)
            total_query = text(f"""
                SELECT COUNT(*) as total
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
            
            """)
            total_result = connection.execute(total_query, params)
            total_released = total_result.fetchone()[0]
            
            # 2. Active Products (not expired, not canceled)
            today = date.today()
            active_query = text(f"""
                SELECT COUNT(*) as active
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND (expiry_date IS NULL OR expiry_date >= :today)
                
            """)
            params_active = {**params, 'today': today}
            active_result = connection.execute(active_query, params_active)
            active_products = active_result.fetchone()[0]
            
            # 3. Expired Products
            expired_query = text(f"""
                SELECT COUNT(*) as expired
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND expiry_date IS NOT NULL
                AND expiry_date < :today
            
            """)
            expired_result = connection.execute(expired_query, params_active)
            expired_products = expired_result.fetchone()[0]
            
            # 4. My Uploads Today
            today_start = datetime.combine(today, datetime.min.time())
            today_query = text(f"""
                SELECT COUNT(*) as today_uploads
                FROM fda_drug_registrations
                WHERE DATE(date_uploaded) = :today
                {user_filter}
            """)
            params_today = {**params, 'today': today}
            today_result = connection.execute(today_query, params_today)
            uploads_today = today_result.fetchone()[0]
            
            # 5. My Uploads Yesterday
            yesterday = today - timedelta(days=1)
            yesterday_query = text(f"""
                SELECT COUNT(*) as yesterday_uploads
                FROM fda_drug_registrations
                WHERE DATE(date_uploaded) = :yesterday
                {user_filter}
            """)
            params_yesterday = {**params, 'yesterday': yesterday}
            yesterday_result = connection.execute(yesterday_query, params_yesterday)
            uploads_yesterday = yesterday_result.fetchone()[0]
            
            # 6. My Uploads This Month
            month_start = today.replace(day=1)
            month_query = text(f"""
                SELECT COUNT(*) as month_uploads
                FROM fda_drug_registrations
                WHERE DATE(date_uploaded) >= :month_start
                {user_filter}
            """)
            params_month = {**params, 'month_start': month_start}
            month_result = connection.execute(month_query, params_month)
            uploads_this_month = month_result.fetchone()[0]
            
            # 7. Duplicate Records (same registration_number, multiple entries)
            duplicate_query = text(f"""
                SELECT COUNT(DISTINCT registration_number) as duplicates
                FROM fda_drug_registrations
                WHERE registration_number IN (
                    SELECT registration_number
                    FROM fda_drug_registrations
                    WHERE (is_canceled IS NULL OR is_canceled = 'N')
                    GROUP BY registration_number
                    HAVING COUNT(*) > 1
                )
            """)
            duplicate_result = connection.execute(duplicate_query, params)
            duplicate_records = duplicate_result.fetchone()[0]
            
            # 8. Cancelled Records
            cancelled_query = text(f"""
                SELECT COUNT(*) as cancelled
                FROM fda_drug_registrations
                WHERE is_canceled = 'Y'
            """)
            cancelled_result = connection.execute(cancelled_query, params)
            cancelled_records = cancelled_result.fetchone()[0]
            
            return {
                "total_manual_application_released": total_released,
                "active_products": active_products,
                "expired_products": expired_products,
                "uploads_today": uploads_today,
                "uploads_yesterday": uploads_yesterday,
                "uploads_this_month": uploads_this_month,
                "duplicate_records": duplicate_records,
                "cancelled_records": cancelled_records,
                "last_updated": datetime.now().isoformat()
            }
            
    finally:
        engine.dispose()


# ==================== UPLOAD HISTORY ====================
def get_upload_history(
    uploaded_by: Optional[str] = None,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get daily upload count for the last N days
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            user_filter = ""
            params = {'days': days}
            
            if uploaded_by:
                user_filter = " AND uploaded_by = :uploaded_by"
                params['uploaded_by'] = uploaded_by
            
            history_query = text(f"""
                SELECT 
                    DATE(date_uploaded) as upload_date,
                    COUNT(*) as count
                FROM fda_drug_registrations
                WHERE date_uploaded >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
                {user_filter}
                GROUP BY DATE(date_uploaded)
                ORDER BY upload_date DESC
            """)
            
            result = connection.execute(history_query, params)
            
            history = []
            for row in result:
                history.append({
                    'date': row[0].isoformat() if row[0] else None,
                    'count': row[1]
                })
            
            return history
            
    finally:
        engine.dispose()


# ==================== EXPIRY ANALYSIS ====================
def get_expiry_analysis(uploaded_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze expiry dates
    """
    engine = get_fda_db_engine()
    
    try:
        with engine.connect() as connection:
            user_filter = ""
            params = {}
            
            if uploaded_by:
                user_filter = " AND uploaded_by = :uploaded_by"
                params['uploaded_by'] = uploaded_by
            
            today = date.today()
            days_30 = today + timedelta(days=30)
            month_end = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            year_end = today.replace(month=12, day=31)
            
            # Expiring Soon (within 30 days)
            soon_query = text(f"""
                SELECT COUNT(*) as count
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND expiry_date BETWEEN :today AND :days_30
                {user_filter}
            """)
            params_soon = {**params, 'today': today, 'days_30': days_30}
            soon_result = connection.execute(soon_query, params_soon)
            expiring_soon = soon_result.fetchone()[0]
            
            # Expiring This Month
            month_query = text(f"""
                SELECT COUNT(*) as count
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND expiry_date BETWEEN :today AND :month_end
                {user_filter}
            """)
            params_month = {**params, 'today': today, 'month_end': month_end}
            month_result = connection.execute(month_query, params_month)
            expiring_this_month = month_result.fetchone()[0]
            
            # Expiring This Year
            year_query = text(f"""
                SELECT COUNT(*) as count
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND expiry_date BETWEEN :today AND :year_end
                {user_filter}
            """)
            params_year = {**params, 'today': today, 'year_end': year_end}
            year_result = connection.execute(year_query, params_year)
            expiring_this_year = year_result.fetchone()[0]
            
            # Already Expired
            expired_query = text(f"""
                SELECT COUNT(*) as count
                FROM fda_drug_registrations
                WHERE (is_canceled IS NULL OR is_canceled = 'N')
                AND expiry_date < :today
                {user_filter}
            """)
            expired_result = connection.execute(expired_query, {**params, 'today': today})
            already_expired = expired_result.fetchone()[0]
            
            return {
                "expiring_soon_30_days": expiring_soon,
                "expiring_this_month": expiring_this_month,
                "expiring_this_year": expiring_this_year,
                "already_expired": already_expired
            }
            
    finally:
        engine.dispose()