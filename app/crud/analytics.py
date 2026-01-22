# app/crud/analytics.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.main_db import MainDB


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
