from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.monitoring import (
    UsersTasksResponse,
    AllRecordsResponse,
    UserTaskSummary,
    TaskStatusBreakdown,
    ReleaseListResponse,
    OverviewSummaryResponse,
    CprTrendResponse,
    ProcessingTrendResponse,
    ProcessingBreakdownResponse,
    SummaryResponse,
)
from app.crud import monitoring as crud_monitoring  
from app.models.group import Group

router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring"],
)


@router.get(
    "/users-tasks",
    response_model=UsersTasksResponse,
    summary="All users with their current task count breakdown",
)
def get_users_tasks(
    group_id: Optional[int] = Query(None, description="Filter by group ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns all active users joined with their task counts from
    application_logs. Matches via username OR alias.
    Returns approved / disapproved / on_process / total per user.
    """
    rows = crud_monitoring.get_users_task_summary(db, group_id=group_id)

    data = [
        UserTaskSummary(
            user_id=user.id,
            username=user.username,
            full_name=f"{user.first_name} {user.surname}".strip(),
            position=user.position,
            group_name=user.groups[0].name if user.groups else None,
            role=user.role.value,
            is_active=user.is_active,
            tasks=TaskStatusBreakdown(
                completed=int(completed),
                in_progress=int(in_progress),
                total=int(total),
            ),
        )
        for user, total, completed, in_progress in rows
    ]

    return UsersTasksResponse(total_users=len(data), data=data)


@router.get("/all-records", response_model=AllRecordsResponse)
def get_all_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    sort_col: str = Query("date"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$"),
    application_status: Optional[str] = Query(
        None, description="COMPLETED | IN PROGRESS"
    ),
    dtn: Optional[str] = Query(None, description="Partial DTN text search"),
    app_step: Optional[str] = Query(
        None, description="e.g. Decking, Checking, Quality Evaluation"
    ),
    dtn_date_from: Optional[str] = Query(
        None,
        description=(
            "Lower bound of DTN date range (YYYYMMDD). "
            "Compared against the first 8 digits of DB_DTN. "
            "Example: 20230101"
        ),
        min_length=8,
        max_length=8,
    ),
    dtn_date_to: Optional[str] = Query(
        None,
        description=(
            "Upper bound of DTN date range (YYYYMMDD). "
            "Compared against the first 8 digits of DB_DTN. "
            "Example: 20261231"
        ),
        min_length=8,
        max_length=8,
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = crud_monitoring.get_all_records(
        db=db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        sort_col=sort_col,
        sort_dir=sort_dir,
        application_status=application_status,
        dtn=dtn,
        app_step=app_step,
        dtn_date_from=dtn_date_from,
        dtn_date_to=dtn_date_to,
    )
    return AllRecordsResponse(**result)


@router.get("/groups", summary="List all groups for filtering")
def get_groups(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    groups = db.query(Group).order_by(Group.name).all()
    return [{"id": g.id, "name": g.name} for g in groups]


# -----------------------------
# SEAN Release endpoints
# -----------------------------
@router.get(
    "/release",
    response_model=ReleaseListResponse,
    summary="Paginated release records from MainDB",
)
def get_release(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=1000),
    search: Optional[str] = Query(None),
    app_status: Optional[str] = Query(None),
    type_doc_released: Optional[str] = Query(None),
    date_released_from: Optional[str] = Query(None),
    date_released_to: Optional[str] = Query(None),
    secpa_exp_from: Optional[str] = Query(None),
    secpa_exp_to: Optional[str] = Query(None),
    sort_by: str = Query("DB_DATE_EXCEL_UPLOAD"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = crud_monitoring.get_release_records(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        app_status=app_status,
        type_doc_released=type_doc_released,
        date_released_from=date_released_from,
        date_released_to=date_released_to,
        secpa_exp_from=secpa_exp_from,
        secpa_exp_to=secpa_exp_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ReleaseListResponse(**result)


@router.get(
    "/release/app-status-types",
    summary="Unique App Status values for dropdown",
)
def get_app_status_types(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    values = crud_monitoring.get_release_app_statuses(db)
    return {"app_status_types": values}


@router.get(
    "/release/doc-types",
    summary="Unique Type Doc Released values for dropdown",
)
def get_doc_types(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    values = crud_monitoring.get_release_doc_types(db)
    return {"doc_types": values}


# -----------------------------
# Overview KPI Summary
# -----------------------------
@router.get(
    "/overview-summary",
    response_model=OverviewSummaryResponse,
    summary="KPI counts for Overview cards",
)
def overview_summary_endpoint(          # ← renamed: was get_overview_summary
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud_monitoring.get_overview_summary(db)


# -----------------------------
# CPR Trend (Received & Released)
# -----------------------------
@router.get(
    "/cpr-trend",
    response_model=CprTrendResponse,
    summary="Monthly trend of received and released CPR drug products",
)
def cpr_trend_endpoint(                 # ← renamed: was get_cpr_trend
    year: Optional[int] = Query(None, description="Filter by year (e.g. 2025)"),
    country_type: Optional[str] = Query(
        None,
        description="Country column to filter: manufacturer|trader|repacker|importer|distributor",
    ),
    country: Optional[str] = Query(None, description="Specific country value to filter on"),
    doc_type: Optional[str] = Query(None, description="Filter by document type released (exact match)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns monthly received vs released counts for CPR drug products.
    Optionally filter by year, country (based on chosen country type), and document type.
    """
    return crud_monitoring.get_cpr_trend(
        db=db,
        year=year,
        country_type=country_type,
        country=country,
        doc_type=doc_type,
    )


# ---------------------------------------------------------------------------
# Processing Trend  — monthly / yearly received vs released line chart
# ---------------------------------------------------------------------------
@router.get(
    "/processing-trend",
    response_model=ProcessingTrendResponse,
    summary="Monthly or yearly received vs released counts with categorical filters",
)
def processing_trend_endpoint(
    group_by: str = Query(
        "month",
        regex="^(month|year)$",
    ),
    year: Optional[int] = Query(None, description="Restrict to a single year, e.g. 2025"),
    date_from: Optional[str] = Query(        
        None,
        description="Lower bound on DB_DATE_RECEIVED_CENT (YYYY-MM-DD)",
    ),
    date_to: Optional[str] = Query(         
        None,
        description="Upper bound on DB_DATE_RECEIVED_CENT (YYYY-MM-DD)",
    ),
    doc_type: Optional[str] = Query(None),
    processing_type: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    app_status: Optional[str] = Query(None),
    app_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud_monitoring.get_processing_trend(
        db=db,
        year=year,
        date_from=date_from,       
        date_to=date_to,           
        doc_type=doc_type,
        processing_type=processing_type,
        entry_type=entry_type,
        app_status=app_status,
        app_type=app_type,
        group_by=group_by,
    )

# ---------------------------------------------------------------------------
# Processing Breakdown  — count grouped by one categorical dimension
# ---------------------------------------------------------------------------

@router.get(
    "/processing-breakdown",
    response_model=ProcessingBreakdownResponse,
    summary="Record counts grouped by a single categorical dimension (pie / bar)",
)
def processing_breakdown_endpoint(      # ← renamed: was get_processing_breakdown
    dimension: str = Query(
        "doc_type",
        regex="^(doc_type|processing_type|entry_type|app_status|app_type)$",
        description=(
            "Column to group by: "
            "doc_type | processing_type | entry_type | app_status | app_type"
        ),
    ),
    year: Optional[int] = Query(None, description="Restrict to a single year"),
    date_from: Optional[str] = Query(
        None,
        description="Lower bound on DB_DATE_RECEIVED_CENT (YYYY-MM-DD)",
    ),
    date_to: Optional[str] = Query(
        None,
        description="Upper bound on DB_DATE_RECEIVED_CENT (YYYY-MM-DD)",
    ),
    doc_type: Optional[str] = Query(None, description="Filter by DB_TYPE_DOC_RELEASED"),
    processing_type: Optional[str] = Query(None, description="Filter by DB_PROCESSING_TYPE"),
    entry_type: Optional[str] = Query(None, description="Filter by DB_ENTRY_TYPE"),
    app_status: Optional[str] = Query(None, description="Filter by DB_APP_STATUS"),
    app_type: Optional[str] = Query(None, description="Filter by DB_APP_TYPE"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Groups MainDB records by one categorical column and returns a sorted list
    of `{ label, count }` pairs — ready to feed a pie or horizontal bar chart.

    The same five filter dropdowns are returned alongside the data.
    """
    return crud_monitoring.get_processing_breakdown(
        db=db,
        dimension=dimension,
        year=year,
        doc_type=doc_type,
        processing_type=processing_type,
        entry_type=entry_type,
        app_status=app_status,
        app_type=app_type,
        date_from=date_from,
        date_to=date_to,
    )

@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Carry over / received / processed / pending per app type",
)
def summary_endpoint(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    year: Optional[int] = Query(None),
    doc_type: Optional[str] = Query(None),
    processing_type: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    app_status: Optional[str] = Query(None),
    app_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud_monitoring.get_summary(
        db=db,
        date_from=date_from,
        date_to=date_to,
        year=year,
        doc_type=doc_type,
        processing_type=processing_type,
        entry_type=entry_type,
        app_status=app_status,
        app_type=app_type,
    )
