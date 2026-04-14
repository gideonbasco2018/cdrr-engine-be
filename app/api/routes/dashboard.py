# app/api/routes/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Literal
from datetime import date
 
from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import dashboard as crud_dashboard
from app.crud import dashboard_chart as crud_chart
from app.schemas.dashboard import StatResponse, CombinedStatsResponse
from app.schemas.dashboard_chart import ChartResponse
from app.crud import dashboard_recent as crud_recent
from app.schemas.recent_applications import RecentApplicationsResponse

router = APIRouter(
    prefix="/api/dashboard/stats",
    tags=["Dashboard Stats"],
)


# ─────────────────────────────────────────────────────────
# Impersonation helper
# ─────────────────────────────────────────────────────────
def _effective_username(
    current_user,
    impersonate: Optional[str],
) -> str:
    """
    Resolution order:
    1. ?impersonate=<username>  →  only honoured when current_user is admin
    2. current_user.username    →  default (own stats)
    """
    if impersonate and getattr(current_user, "is_admin", False):
        return impersonate
    return current_user.username


# ─────────────────────────────────────────────────────────
# Shared query params (reused across all 3 endpoints)
# ─────────────────────────────────────────────────────────
def _common_params(
    date_from:   Optional[date] = Query(None, description="Start date filter  YYYY-MM-DD"),
    date_to:     Optional[date] = Query(None, description="End date filter    YYYY-MM-DD"),
    impersonate: Optional[str]  = Query(None, description="Admin only: target username"),
):
    return {"date_from": date_from, "date_to": date_to, "impersonate": impersonate}


# ─────────────────────────────────────────────────────────
# 1. GET /dashboard/stats/received
# ─────────────────────────────────────────────────────────
@router.get(
    "/received",
    response_model=StatResponse,
    summary="Total applications received by the current user",
)
def get_received(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_received(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Total Received",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# 2. GET /dashboard/stats/completed
# ─────────────────────────────────────────────────────────
@router.get(
    "/completed",
    response_model=StatResponse,
    summary="Total completed applications for the current user",
)
def get_completed(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_completed(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Completed",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# 3. GET /dashboard/stats/on-process
# ─────────────────────────────────────────────────────────
@router.get(
    "/on-process",
    response_model=StatResponse,
    summary="Total on-process applications for the current user",
)
def get_on_process(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_on_process(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="On Process",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# BONUS: GET /dashboard/stats/summary  (all 3 in one call)
# ─────────────────────────────────────────────────────────
@router.get(
    "/summary",
    response_model=CombinedStatsResponse,
    summary="All 3 KPI stats in one request",
)
def get_summary(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    stats    = crud_dashboard.get_stats_summary(
        db, username, params["date_from"], params["date_to"]
    )
    return CombinedStatsResponse(
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
        **stats,
    )


# ═════════════════════════════════════════════════════════
# CHART  (/api/dashboard/chart)
# ═════════════════════════════════════════════════════════
 
# ─────────────────────────────────────────────────────────
# GET /api/dashboard/chart
# ─────────────────────────────────────────────────────────
@router.get(
    "/chart",
    response_model=ChartResponse,
    summary="Time-series data for the Insights chart and data table",
    description="""
Returns aggregated **received / completed / on_process** counts
grouped by the requested breakdown:
 
| breakdown | label examples      | typical usage                        |
|-----------|---------------------|--------------------------------------|
| `day`     | `'1'` … `'31'`     | single month  e.g. Mar 2026          |
| `month`   | `'Jan'` … `'Dec'`  | single year   e.g. 2026              |
| `year`    | `'2022'` … `'2026'`| all-time — omit date params          |
 
The response includes pre-computed **totals** and **overall_completed_rate**.
    """,
)
def get_chart(
    breakdown: Literal["day", "month", "year"] = Query(
        "day",
        description="Aggregation granularity",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Inclusive start date  YYYY-MM-DD",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Inclusive end date    YYYY-MM-DD",
    ),
    impersonate: Optional[str] = Query(
        None,
        description="Admin only — view another user's chart data",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
        )
 
    username = _effective_username(current_user, impersonate)
 
    try:
        return crud_chart.get_chart_data(
            db=db,
            username=username,
            breakdown=breakdown,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
 

@router.get(
    "/recent-applications",
    response_model=RecentApplicationsResponse,
    summary="Most recent application log entries for the current user",
)
def get_recent_applications(
    limit: int = Query(
        default=10, ge=1, le=50,
        description="Number of rows to return (max 50)",
    ),
    impersonate: Optional[str] = Query(
        None, description="Admin only: view another user's data",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, impersonate)
 
    data = crud_recent.get_recent_applications(
        db=db,
        username=username,
        limit=limit,
    )
 
    return RecentApplicationsResponse(
        data=data,
        count=len(data),
        username=username,
    )
 
 