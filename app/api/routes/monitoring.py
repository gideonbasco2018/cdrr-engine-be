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
    # ── DTN date range ────────────────────────────────────────────────────────
    # Both params are 8-digit strings (YYYYMMDD) built by the frontend.
    # The frontend pads omitted month → 01/12 and day → 01/31 automatically,
    # so a year-only range of 2023→2026 arrives as:
    #   dtn_date_from=20230101  dtn_date_to=20261231
    #
    # The CRUD validates that each value is exactly 8 digits before filtering.
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
    # ─────────────────────────────────────────────────────────────────────────
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