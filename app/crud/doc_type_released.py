from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.models.main_db import MainDB


def get_doc_type_released_rows(
    db: Session,
    app_type: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
):
    """
    Query DB_TYPE_DOC_RELEASED counts grouped by release year and doc_type.
    Uses the same date basis (DB_DATE_RELEASED) as the analytics year summary,
    so the per-doc-type counts and the yearly total line up.
    """
    date_col = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    year_col = func.year(date_col)

    query = db.query(
        year_col.label("year"),
        MainDB.DB_TYPE_DOC_RELEASED.label("doc_type"),
        func.count().label("total"),
    ).filter(
        MainDB.DB_TYPE_DOC_RELEASED.isnot(None),
        MainDB.DB_TYPE_DOC_RELEASED != "",
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        date_col.isnot(None),  # guards against unparseable dates
        year_col >= 2000,
        year_col <= 2100,
    )

    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE == app_type)
    if year_from:
        query = query.filter(year_col >= year_from)
    if year_to:
        query = query.filter(year_col <= year_to)

    return (
        query.group_by(year_col, MainDB.DB_TYPE_DOC_RELEASED)
        .order_by(year_col.asc(), MainDB.DB_TYPE_DOC_RELEASED.asc())
        .all()
    )
