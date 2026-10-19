from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.models.main_db import MainDB


def get_doc_type_released_rows(
    db: Session,
    app_type: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    basis: str = "released",
):
    """
    Query DB_TYPE_DOC_RELEASED counts grouped by year and doc_type.

    basis="released" (default): grouped by release year (DB_DATE_RELEASED).
    basis="received": grouped by the year the application was RECEIVED
                      (DB_DATE_RECEIVED_CENT), counting only records that
                      have been released. Matches analytics year-summary
                      so the per-doc-type counts and the yearly total line up.
    """
    basis = "received" if basis == "received" else "released"

    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rel_year = func.year(rel_date)
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rec_year = func.year(rec_date)

    year_col = rec_year if basis == "received" else rel_year

    filters = [
        MainDB.DB_TYPE_DOC_RELEASED.isnot(None),
        MainDB.DB_TYPE_DOC_RELEASED != "",
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        rel_date.isnot(None),  # guards against unparseable dates
        rel_year >= 2000,
        rel_year <= 2100,
    ]
    if basis == "received":
        filters += [
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
            rec_date.isnot(None),
            rec_year >= 2000,
            rec_year <= 2100,
        ]

    query = db.query(
        year_col.label("year"),
        MainDB.DB_TYPE_DOC_RELEASED.label("doc_type"),
        func.count().label("total"),
    ).filter(*filters)

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
