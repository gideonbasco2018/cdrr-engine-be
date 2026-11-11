# app/crud/hiring_impact.py

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.crud.analytics import _valid_date_cond, _is_completed, _is_in_progress

_YM = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MAX_MONTHS = 120


def _month_range(date_from: str, date_to: str) -> list:
    a, b = _YM.match(date_from or ""), _YM.match(date_to or "")
    if not a or not b:
        raise ValueError("Use the YYYY-MM format for date_from and date_to")
    y, m = int(a.group(1)), int(a.group(2))
    ty, tm = int(b.group(1)), int(b.group(2))
    months = []
    while (y, m) <= (ty, tm):
        months.append(f"{y}-{m:02d}")
        if len(months) > MAX_MONTHS:
            raise ValueError(f"The range is limited to {MAX_MONTHS} months")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def get_hiring_impact_series(db: Session, date_from: str, date_to: str) -> list:
    """
    Per month: received, released and backlog (in progress at month end).

    received : valid Date Received in that month
    released : COMPLETED with a valid Date Released in that month
               (same rule as the Analytics line chart)
    backlog  : received on or before the month end AND not released yet at
               that time, i.e. currently IN PROGRESS, or COMPLETED with a
               release month after the month being measured.

    Limit: the status column only holds the CURRENT status, so the backlog
    history is reconstructed from dates, not from real snapshots.
    """
    months = _month_range(date_from, date_to)
    if not months:
        return []

    rec = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rel = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rec_ym = func.date_format(rec, "%Y-%m")
    rel_ym = func.date_format(rel, "%Y-%m")
    rec_valid = _valid_date_cond(MainDB.DB_DATE_RECEIVED_CENT)
    rel_valid = _valid_date_cond(MainDB.DB_DATE_RELEASED)

    received_rows = (
        db.query(rec_ym.label("ym"), func.count(MainDB.DB_ID).label("n"))
        .filter(rec_valid)
        .group_by("ym")
        .all()
    )
    released_rows = (
        db.query(rel_ym.label("ym"), func.count(MainDB.DB_ID).label("n"))
        .filter(rel_valid, _is_completed())
        .group_by("ym")
        .all()
    )
    open_rows = (
        db.query(rec_ym.label("ym"), func.count(MainDB.DB_ID).label("n"))
        .filter(rec_valid, _is_in_progress())
        .group_by("ym")
        .all()
    )
    closed_rows = (
        db.query(
            rec_ym.label("rm"),
            rel_ym.label("lm"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(rec_valid, rel_valid, _is_completed())
        .group_by("rm", "lm")
        .all()
    )

    received = {r.ym: int(r.n or 0) for r in received_rows if r.ym}
    released = {r.ym: int(r.n or 0) for r in released_rows if r.ym}
    still_open = [(r.ym, int(r.n or 0)) for r in open_rows if r.ym]
    closed = [(r.rm, r.lm, int(r.n or 0)) for r in closed_rows if r.rm and r.lm]

    series = []
    for ym in months:
        # "YYYY-MM" strings compare correctly as text
        backlog = sum(n for rm, n in still_open if rm <= ym) + sum(
            n for rm, lm, n in closed if rm <= ym < lm
        )
        series.append(
            {
                "month": ym,
                "received": received.get(ym, 0),
                "released": released.get(ym, 0),
                "backlog": backlog,
            }
        )
    return series
