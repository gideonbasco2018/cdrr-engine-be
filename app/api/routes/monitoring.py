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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns all active users joined with their task counts from
    application_logs. Matches via username OR alias.
    Returns approved / disapproved / on_process / total per user.
    """
    rows = crud_monitoring.get_users_task_summary(db)

    data = [
        UserTaskSummary(
            user_id=user.id,
            username=user.username,
            full_name=f"{user.first_name} {user.surname}".strip(),
            position=user.position,
            role=user.role.value,
            is_active=user.is_active,
            tasks=TaskStatusBreakdown(
                completed=int(completed),
                in_progress=int(in_progress),
                total=int(total),
            ),
        )
        for user, total, completed, in_progress in rows   # ← updated unpacking
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
    application_status: Optional[str] = Query(None, description="COMPLETED | IN PROGRESS"),  # ← NEW
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
        application_status=application_status,  # ← NEW
    )
    return AllRecordsResponse(**result)