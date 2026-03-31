# app/api/routes/dashboard.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import dashboard as crud_dashboard
from app.schemas.dashboard import StatResponse, CombinedStatsResponse


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