# app/crud/analytics.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from app.models.main_db import MainDB
from datetime import datetime
from typing import List


def _build_date_filters(date_column, year: int, month: int | None, day: int | None):
    """
    Builds SQL filters for TEXT date fields using STR_TO_DATE
    Expected format: YYYY-MM-DD (or compatible)
    """
    filters = [
        func.year(func.str_to_date(date_column, "%Y-%m-%d")) == year
    ]

    if month:
        filters.append(
            func.month(func.str_to_date(date_column, "%Y-%m-%d")) == month
        )

    if day:
        filters.append(
            func.day(func.str_to_date(date_column, "%Y-%m-%d")) == day
        )

    return filters


def count_received_fdac(
    db: Session,
    year: int,
    month: int | None = None,
    day: int | None = None,
) -> int:
    filters = _build_date_filters(
        MainDB.DB_DATE_RECEIVED_FDAC, year, month, day
    )

    return (
        db.query(func.count(MainDB.DB_ID))
        .filter(MainDB.DB_DATE_RECEIVED_FDAC.isnot(None))
        .filter(*filters)
        .scalar()
        or 0
    )


def count_received_central(
    db: Session,
    year: int,
    month: int | None = None,
    day: int | None = None,
) -> int:
    filters = _build_date_filters(
        MainDB.DB_DATE_RECEIVED_CENT, year, month, day
    )

    return (
        db.query(func.count(MainDB.DB_ID))
        .filter(MainDB.DB_DATE_RECEIVED_CENT.isnot(None))
        .filter(*filters)
        .scalar()
        or 0
    )


def get_monthly_breakdown(db: Session, year: int | None = None) -> List[dict]:
    """
    Get monthly breakdown of received applications (Jan-Dec)
    If year is None, use current year
    """
    if year is None:
        year = datetime.now().year
    
    monthly_data = []
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    for month_num in range(1, 13):
        fdac_count = count_received_fdac(db=db, year=year, month=month_num)
        central_count = count_received_central(db=db, year=year, month=month_num)
        
        monthly_data.append({
            "period": month_names[month_num - 1],
            "month": month_num,
            "year": year,
            "fdac": fdac_count,
            "central": central_count,
            "total": fdac_count + central_count,
        })
    
    return monthly_data


def get_yearly_breakdown(db: Session, num_years: int = 5) -> List[dict]:
    """
    Get yearly breakdown of received applications (last N years)
    """
    current_year = datetime.now().year
    yearly_data = []
    
    for year in range(current_year - num_years + 1, current_year + 1):
        fdac_count = count_received_fdac(db=db, year=year)
        central_count = count_received_central(db=db, year=year)
        
        yearly_data.append({
            "period": str(year),
            "year": year,
            "fdac": fdac_count,
            "central": central_count,
            "total": fdac_count + central_count,
        })
    
    return yearly_data