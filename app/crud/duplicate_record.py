# app/crud/duplicate_record.py

import math
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.main_db import MainDB

# Whitelist lang — para hindi natin pagana ang raw column name galing sa query param
DUPLICATE_COLUMN_MAP = {
    "dtn": MainDB.DB_DTN,
    "reg_no": MainDB.DB_REG_NO,
}


def get_duplicate_groups(db: Session, by: Literal["dtn", "reg_no"]):
    """
    Step 1 lang: hanapin ang mga value na paulit-ulit (group + having count > 1).
    Maliit lang ito (listahan ng unique keys), kaya hindi natin pino-paginate.
    """
    column = DUPLICATE_COLUMN_MAP[by]

    dupe_groups = (
        db.query(column.label("dupe_key"), func.count(MainDB.DB_ID).label("cnt"))
        .filter(column.isnot(None))
        .group_by(column)
        .having(func.count(MainDB.DB_ID) > 1)
        .all()
    )
    return dupe_groups


def get_duplicate_records(
    db: Session,
    by: Literal["dtn", "reg_no"],
    page: int = 1,
    page_size: int = 50,
):
    """
    Tumukoy ng totoong duplicate records sa buong main_db table
    (hindi lang sa current page ng UI) — base sa DTN o Registration No.

    Pinapaginate ang `records` para hindi sumabog ang response size
    (lalo na sa Swagger UI na nagiging stuck sa malaking JSON).
    """
    dupe_groups = get_duplicate_groups(db, by)

    if not dupe_groups:
        return [], [], 0

    column = DUPLICATE_COLUMN_MAP[by]
    dupe_keys = [g.dupe_key for g in dupe_groups]

    # Total count ng lahat ng duplicate records (para sa pagination metadata)
    total_count = (
        db.query(func.count(MainDB.DB_ID))
        .filter(column.in_(dupe_keys))
        .scalar()
    )

    # Actual paginated fetch — LIMIT/OFFSET
    offset = (page - 1) * page_size
    records = (
        db.query(MainDB)
        .filter(column.in_(dupe_keys))
        .order_by(column, MainDB.DB_ID)
        .limit(page_size)
        .offset(offset)
        .all()
    )

    return dupe_groups, records, total_count