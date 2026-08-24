# app/crud/gmp_dashboard_chart.py
# GMP counterpart of app/crud/dashboard_chart.py — reuses the same
# ChartDataPoint / ChartResponse schemas since they carry no licensing-specific
# fields.

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case, Integer
from typing import Optional, List
from datetime import date

from app.models.gmp_record import GMPApplicationLogs
from app.schemas.dashboard_chart import ChartDataPoint, ChartResponse

_MONTH_LABELS = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _base_query(
    db: Session,
    username: str,
    date_from: Optional[date],
    date_to: Optional[date],
):
    q = db.query(GMPApplicationLogs).filter(
        GMPApplicationLogs.user_name == username,
        GMPApplicationLogs.del_thread.in_(["Close", "Open"]),
    )
    if date_from:
        q = q.filter(func.date(GMPApplicationLogs.start_date) >= date_from)
    if date_to:
        q = q.filter(func.date(GMPApplicationLogs.start_date) <= date_to)
    return q


def _agg_columns():
    received = func.count(GMPApplicationLogs.id).label("received")

    completed = func.sum(
        case(
            (GMPApplicationLogs.application_status == "COMPLETED", 1),
            else_=0,
        )
    ).label("completed")

    on_process = func.sum(
        case(
            (
                (GMPApplicationLogs.application_status == "IN PROGRESS") &
                (GMPApplicationLogs.del_thread == "Open"),
                1,
            ),
            else_=0,
        )
    ).label("on_process")

    return received, completed, on_process


def get_daily_chart(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    received, completed, on_process = _agg_columns()
    day_col = func.date(GMPApplicationLogs.start_date).label("bucket")

    rows = (
        _base_query(db, username, date_from, date_to)
        .with_entities(day_col, received, completed, on_process)
        .group_by(day_col)
        .order_by(day_col)
        .all()
    )

    return [
        ChartDataPoint(
            label=str(row.bucket.day) if hasattr(row.bucket, "day") else str(row.bucket),
            received=row.received,
            completed=int(row.completed or 0),
            on_process=int(row.on_process or 0),
        )
        for row in rows
    ]


def get_monthly_chart(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    received, completed, on_process = _agg_columns()

    year_col = extract("year", GMPApplicationLogs.start_date).cast(Integer).label("yr")
    month_col = extract("month", GMPApplicationLogs.start_date).cast(Integer).label("mo")

    rows = (
        _base_query(db, username, date_from, date_to)
        .with_entities(year_col, month_col, received, completed, on_process)
        .group_by(year_col, month_col)
        .order_by(year_col, month_col)
        .all()
    )

    return [
        ChartDataPoint(
            label=_MONTH_LABELS[row.mo],
            received=row.received,
            completed=int(row.completed or 0),
            on_process=int(row.on_process or 0),
        )
        for row in rows
    ]


def get_yearly_chart(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    received, completed, on_process = _agg_columns()

    year_col = extract("year", GMPApplicationLogs.start_date).cast(Integer).label("yr")

    rows = (
        _base_query(db, username, date_from, date_to)
        .with_entities(year_col, received, completed, on_process)
        .group_by(year_col)
        .order_by(year_col)
        .all()
    )

    return [
        ChartDataPoint(
            label=str(row.yr),
            received=row.received,
            completed=int(row.completed or 0),
            on_process=int(row.on_process or 0),
        )
        for row in rows
    ]


def get_chart_data(
    db: Session,
    username: str,
    breakdown: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> ChartResponse:
    breakdown = breakdown.lower().strip()

    if breakdown == "day":
        data = get_daily_chart(db, username, date_from, date_to)
    elif breakdown == "month":
        data = get_monthly_chart(db, username, date_from, date_to)
    elif breakdown == "year":
        data = get_yearly_chart(db, username, date_from, date_to)
    else:
        raise ValueError(f"Invalid breakdown '{breakdown}'. Must be 'day', 'month', or 'year'.")

    total_received = sum(p.received for p in data)
    total_completed = sum(p.completed for p in data)
    total_on_process = sum(p.on_process for p in data)

    return ChartResponse(
        username=username,
        breakdown=breakdown,
        date_from=date_from,
        date_to=date_to,
        data=data,
        total_received=total_received,
        total_completed=total_completed,
        total_on_process=total_on_process,
    )
