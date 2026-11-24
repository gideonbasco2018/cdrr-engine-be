# app/crud/dashboard_chart.py

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case, Integer
from typing import Optional, List
from datetime import date

from app.models.application_logs import ApplicationLogs
from app.schemas.dashboard_chart import ChartDataPoint, ChartResponse
from app.crud.dashboard_filters import apply_counting_filters

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────
_MONTH_LABELS = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────
def _base_query(
    db: Session,
    user_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
):
    """
    Shared base scoped to:
    - user_id
    - del_thread IN ('Close', 'Open')
    - re-route / re-assign rows excluded
    - optional start_date range
    """
    q = apply_counting_filters(db.query(ApplicationLogs), user_id)
    if date_from:
        q = q.filter(func.date(ApplicationLogs.start_date) >= date_from)
    if date_to:
        q = q.filter(func.date(ApplicationLogs.start_date) <= date_to)
    return q


def _agg_columns():
    """
    Returns SQLAlchemy column expressions for received / completed / on_process.
    Reused across all three breakdown modes.
    """
    received = func.count(ApplicationLogs.id).label("received")

    completed = func.sum(
        case(
            (ApplicationLogs.application_status == "COMPLETED", 1),
            else_=0,
        )
    ).label("completed")

    on_process = func.sum(
        case(
            (
                (ApplicationLogs.application_status == "IN PROGRESS")
                & (ApplicationLogs.del_thread == "Open"),
                1,
            ),
            else_=0,
        )
    ).label("on_process")

    return received, completed, on_process


# ─────────────────────────────────────────────────────────
# 1. Daily breakdown
# ─────────────────────────────────────────────────────────
def get_daily_chart(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    """
    Groups by calendar day of start_date.
    Returns one ChartDataPoint per day that has at least one record.
    """
    received, completed, on_process = _agg_columns()

    day_col = func.date(ApplicationLogs.start_date).label("bucket")

    rows = (
        _base_query(db, user_id, date_from, date_to)
        .with_entities(day_col, received, completed, on_process)
        .group_by(day_col)
        .order_by(day_col)
        .all()
    )

    return [
        ChartDataPoint(
            label=(
                str(row.bucket.day) if hasattr(row.bucket, "day") else str(row.bucket)
            ),
            received=row.received,
            completed=int(row.completed or 0),
            on_process=int(row.on_process or 0),
        )
        for row in rows
    ]


# ─────────────────────────────────────────────────────────
# 2. Monthly breakdown
# ─────────────────────────────────────────────────────────
def get_monthly_chart(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    """
    Groups by (year, month_number) of start_date.
    Label is the short month name: 'Jan', 'Feb', ...
    """
    received, completed, on_process = _agg_columns()

    year_col = extract("year", ApplicationLogs.start_date).cast(Integer).label("yr")
    month_col = extract("month", ApplicationLogs.start_date).cast(Integer).label("mo")

    rows = (
        _base_query(db, user_id, date_from, date_to)
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


# ─────────────────────────────────────────────────────────
# 3. Yearly breakdown
# ─────────────────────────────────────────────────────────
def get_yearly_chart(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[ChartDataPoint]:
    """
    Groups by calendar year of start_date.
    Label is the 4-digit year string: '2022', '2023', ...
    """
    received, completed, on_process = _agg_columns()

    year_col = extract("year", ApplicationLogs.start_date).cast(Integer).label("yr")

    rows = (
        _base_query(db, user_id, date_from, date_to)
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


# ─────────────────────────────────────────────────────────
# Dispatcher used by the router
# ─────────────────────────────────────────────────────────
def get_chart_data(
    db: Session,
    user_id: int,
    username: str,  # display only (response payload)
    breakdown: str,  # 'day' | 'month' | 'year'
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> ChartResponse:
    """
    Single entry point — picks the right aggregation based on `breakdown`.
    Calculates totals server-side so the frontend doesn't have to reduce.
    """
    breakdown = breakdown.lower().strip()

    if breakdown == "day":
        data = get_daily_chart(db, user_id, date_from, date_to)
    elif breakdown == "month":
        data = get_monthly_chart(db, user_id, date_from, date_to)
    elif breakdown == "year":
        data = get_yearly_chart(db, user_id, date_from, date_to)
    else:
        raise ValueError(
            f"Invalid breakdown '{breakdown}'. Must be 'day', 'month', or 'year'."
        )

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


def _completed_by_accomplished(
    db: Session,
    user_id: int,
    breakdown: str,
    date_from: Optional[date],
    date_to: Optional[date],
) -> dict:
    """{label: count} ng COMPLETED, naka-group by accomplished_date."""
    col = ApplicationLogs.accomplished_date

    if breakdown == "day":
        exprs = [func.date(col).label("d")]
    elif breakdown == "month":
        exprs = [
            extract("year", col).cast(Integer).label("yr"),
            extract("month", col).cast(Integer).label("mo"),
        ]
    else:
        exprs = [extract("year", col).cast(Integer).label("yr")]

    q = apply_counting_filters(db.query(ApplicationLogs), user_id).filter(
        ApplicationLogs.application_status == "COMPLETED",
        col.isnot(None),
    )
    if date_from:
        q = q.filter(func.date(col) >= date_from)
    if date_to:
        q = q.filter(func.date(col) <= date_to)

    rows = (
        q.with_entities(*exprs, func.count(ApplicationLogs.id).label("completed"))
        .group_by(*exprs)
        .all()
    )

    out = {}
    for r in rows:
        if breakdown == "day":
            label = str(r.d.day) if hasattr(r.d, "day") else str(r.d)
        elif breakdown == "month":
            label = _MONTH_LABELS[r.mo]
        else:
            label = str(r.yr)
        out[label] = int(r.completed or 0)
    return out


def _sort_key(label: str, breakdown: str) -> int:
    return _MONTH_LABELS.index(label) if breakdown == "month" else int(label)


def get_chart_data(
    db: Session,
    user_id: int,
    username: str,
    breakdown: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> ChartResponse:
    breakdown = breakdown.lower().strip()

    if breakdown == "day":
        base = get_daily_chart(db, user_id, date_from, date_to)
    elif breakdown == "month":
        base = get_monthly_chart(db, user_id, date_from, date_to)
    elif breakdown == "year":
        base = get_yearly_chart(db, user_id, date_from, date_to)
    else:
        raise ValueError(
            f"Invalid breakdown '{breakdown}'. Must be 'day', 'month', or 'year'."
        )

    completed_map = _completed_by_accomplished(
        db, user_id, breakdown, date_from, date_to
    )

    # received / on_process = by start_date, completed = by accomplished_date
    merged = {
        p.label: ChartDataPoint(
            label=p.label,
            received=p.received,
            completed=completed_map.get(p.label, 0),
            on_process=p.on_process,
        )
        for p in base
    }
    # araw na may completed pero walang na-start
    for label, n in completed_map.items():
        if label not in merged:
            merged[label] = ChartDataPoint(
                label=label, received=0, completed=n, on_process=0
            )

    data = sorted(merged.values(), key=lambda p: _sort_key(p.label, breakdown))

    return ChartResponse(
        username=username,
        breakdown=breakdown,
        date_from=date_from,
        date_to=date_to,
        data=data,
        total_received=sum(p.received for p in data),
        total_completed=sum(p.completed for p in data),
        total_on_process=sum(p.on_process for p in data),
    )
