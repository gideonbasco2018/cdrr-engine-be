# app/api/routes/gmp_dashboard.py
# GMP counterpart of app/api/routes/dashboard.py — same shape (received /
# completed / on-process / summary / chart / recent-applications / detail),
# scoped to GMPRecord / GMPApplicationLogs instead of MainDB / ApplicationLogs.

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Literal
from datetime import date

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import gmp_dashboard as crud_dashboard
from app.crud import gmp_dashboard_chart as crud_chart
from app.crud import gmp_dashboard_recent as crud_recent
from app.crud import gmp_dashboard_detail as crud_detail
from app.schemas.dashboard import StatResponse, CombinedStatsResponse
from app.schemas.dashboard_chart import ChartResponse
from app.schemas.recent_applications import RecentApplicationsResponse
from app.schemas.gmp_dashboard_detail import GMPMetricDetailResponse
from app.models.user import User

router = APIRouter(
    prefix="/api/dashboard/gmp/stats",
    tags=["GMP Dashboard Stats"],
)


def _effective_username(
    current_user,
    impersonate: Optional[int],
    db: Session = None,
) -> str:
    if impersonate and db and current_user.role in ("Admin", "SuperAdmin"):
        user = db.query(User).filter(User.id == impersonate).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user.username
    return current_user.username


def _common_params(
    date_from: Optional[date] = Query(None, description="Start date filter  YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="End date filter    YYYY-MM-DD"),
    impersonate: Optional[int] = Query(
        None, description="Admin only: user_id of target user"
    ),
):
    return {"date_from": date_from, "date_to": date_to, "impersonate": impersonate}


@router.get(
    "/received",
    response_model=StatResponse,
    summary="Total GMP applications received by the current user",
)
def get_received(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"], db)
    value = crud_dashboard.get_total_received(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Total Received",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


@router.get(
    "/completed",
    response_model=StatResponse,
    summary="Total completed GMP applications for the current user",
)
def get_completed(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"], db)
    value = crud_dashboard.get_total_completed(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Completed",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


@router.get(
    "/on-process",
    response_model=StatResponse,
    summary="Total on-process GMP applications for the current user",
)
def get_on_process(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"], db)
    value = crud_dashboard.get_total_on_process(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="On Process",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


@router.get(
    "/summary",
    response_model=CombinedStatsResponse,
    summary="All 3 GMP KPI stats in one request",
)
def get_summary(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"], db)
    stats = crud_dashboard.get_stats_summary(
        db, username, params["date_from"], params["date_to"]
    )
    return CombinedStatsResponse(
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
        **stats,
    )


@router.get(
    "/chart",
    response_model=ChartResponse,
    summary="Time-series data for the GMP Insights chart and data table",
)
def get_chart(
    breakdown: Literal["day", "month", "year"] = Query(
        "day",
        description="Aggregation granularity",
    ),
    date_from: Optional[date] = Query(None, description="Inclusive start date  YYYY-MM-DD"),
    date_to: Optional[date] = Query(None, description="Inclusive end date    YYYY-MM-DD"),
    impersonate: Optional[int] = Query(None, description="Admin only — user_id of target user"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
        )

    username = _effective_username(current_user, impersonate, db)

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
    summary="Most recent GMP application log entries for the current user",
)
def get_recent_applications(
    limit: int = Query(default=10, ge=1, le=500, description="Number of rows to return"),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=10, ge=1, le=50, description="Rows per page (max 50)"),
    impersonate: Optional[int] = Query(None, description="Admin only — user_id of target user"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, impersonate, db)

    data = crud_recent.get_recent_applications(
        db=db,
        username=username,
        limit=limit,
        page=page,
        page_size=page_size,
    )

    return RecentApplicationsResponse(
        data=data["rows"],
        count=len(data["rows"]),
        total=data["total"],
        total_pages=data["total_pages"],
        page=data["page"],
        username=username,
    )


@router.get(
    "/detail",
    response_model=GMPMetricDetailResponse,
    summary="Paginated GMP application log rows for a specific KPI metric",
)
def get_metric_detail(
    metric: str = Query(..., description="KPI to drill into: received | completed | on_process"),
    date_from: Optional[date] = Query(None, description="Inclusive start date  YYYY-MM-DD  (filters start_date)"),
    date_to: Optional[date] = Query(None, description="Inclusive end date    YYYY-MM-DD  (filters start_date)"),
    accomplished_date_from: Optional[date] = Query(None, description="Filter rows where end_date >= this date"),
    accomplished_date_to: Optional[date] = Query(None, description="Filter rows where end_date <= this date"),
    app_step: Optional[str] = Query(None, description="Filter rows by app_step"),
    dtn: Optional[str] = Query(None, description="Filter by DTN (partial match)"),
    sort_by: Optional[str] = Query(None, description="Column to sort by. Currently supported: 'dtn'"),
    sort_dir: Literal["asc", "desc"] = Query("asc", description="Sort direction when sort_by is provided"),
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=10, ge=1, le=500, description="Rows per page (max 500)"),
    impersonate: Optional[int] = Query(None, description="Admin only — user_id of target user"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if metric not in ("received", "completed", "on_process"):
        raise HTTPException(
            status_code=422,
            detail="metric must be one of: received, completed, on_process",
        )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
        )

    if (
        accomplished_date_from
        and accomplished_date_to
        and accomplished_date_from > accomplished_date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="accomplished_date_from must be earlier than or equal to accomplished_date_to.",
        )

    username = _effective_username(current_user, impersonate, db)

    try:
        return crud_detail.get_metric_detail(
            db=db,
            username=username,
            metric=metric,
            date_from=date_from,
            date_to=date_to,
            accomplished_date_from=accomplished_date_from,
            accomplished_date_to=accomplished_date_to,
            app_step=app_step,
            dtn=dtn,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
