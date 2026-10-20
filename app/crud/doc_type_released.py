from types import SimpleNamespace
from sqlalchemy.orm import Session
from sqlalchemy import and_, case, func
from typing import Optional

from app.models.main_db import MainDB
from app.crud.analytics import _is_completed, _doc_key_expr


def get_doc_type_released_rows(
    db: Session,
    app_type: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    basis: str = "released",
):
    """
    Completed releases grouped by year and normalized doc type.
    Completed records whose dates can't be placed in a year are returned
    under year "No Date" (only when no year range filter is applied).
    """
    basis = "received" if basis == "received" else "released"

    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rel_year = func.year(rel_date)
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rec_year = func.year(rec_date)

    year_col = rec_year if basis == "received" else rel_year
    doc_key = _doc_key_expr()

    date_filters = [
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        rel_date.isnot(None),
        rel_year >= 2000,
        rel_year <= 2100,
    ]
    if basis == "received":
        date_filters += [
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
            rec_date.isnot(None),
            rec_year >= 2000,
            rec_year <= 2100,
        ]

    base_filters = [_is_completed(), doc_key != "__NONE__"]

    query = db.query(
        year_col.label("year"),
        doc_key.label("doc_type"),
        func.count().label("total"),
    ).filter(*base_filters, *date_filters)

    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE == app_type)
    if year_from:
        query = query.filter(year_col >= year_from)
    if year_to:
        query = query.filter(year_col <= year_to)

    rows = (
        query.group_by(year_col, doc_key).order_by(year_col.asc(), doc_key.asc()).all()
    )

    if not year_from and not year_to:
        date_ok = case((and_(*date_filters), 1), else_=0)
        nd_query = db.query(
            doc_key.label("doc_type"), func.count().label("total")
        ).filter(*base_filters, date_ok == 0)
        if app_type:
            nd_query = nd_query.filter(MainDB.DB_APP_TYPE == app_type)
        for r in nd_query.group_by(doc_key).all():
            rows.append(
                SimpleNamespace(year="No Date", doc_type=r.doc_type, total=r.total)
            )

    return rows
