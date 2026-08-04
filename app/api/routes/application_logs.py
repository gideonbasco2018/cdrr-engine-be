# app/api/routes/application_logs.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import application_logs as crud_logs
from app.schemas.application_logs import (
    ApplicationLogCreate,
    ApplicationLogUpdate,
    ApplicationLogResponse,
    OpenTasksResponse,
)
from app.models.user import User
from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs

import app.crud.notification as crud_notif
from app.schemas.notification import NotificationCreate
from app.crud.application_logs import toggle_star

router = APIRouter(prefix="/api/application-logs", tags=["Application Logs"])


@router.post(
    "/", response_model=ApplicationLogResponse, status_code=status.HTTP_201_CREATED
)
def create_application_log(
    log_in: ApplicationLogCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:

        log = crud_logs.create(db, log_in=log_in)

        if log_in.deadline_date and log_in.user_name:
            try:

                dtn = str(log.main_db.DB_DTN) if log.main_db else f"LOG#{log.id}"

                if not crud_notif.already_notified_today(
                    db,
                    user_name=log_in.user_name,
                    link_dtn=dtn,
                    title_like="Compliance Task Assigned",
                ):
                    crud_notif.create_notification(
                        db,
                        NotificationCreate(
                            user_name=log_in.user_name,
                            title="📋 Compliance Task Assigned",
                            message=(
                                f"You have been assigned a Compliance task for DTN {dtn}. "
                                f"Deadline: {log_in.deadline_date.strftime('%b %d, %Y')} "
                                f"({log_in.working_days} working days)."
                            ),
                            link_dtn=dtn,
                            app_log_id=log.id,
                        ),
                    )
            except Exception as notif_err:

                print(
                    f"[Notification] Failed to create instant notification: {notif_err}"
                )

        return log

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application log: {str(e)}",
        )


@router.post(
    "/bulk",
    response_model=List[ApplicationLogResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_bulk_application_logs(
    logs_in: List[ApplicationLogCreate],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
        Create multiple application log entries at once

        Useful for bulk operations like:
        - Bulk decking multiple applications
        - Batch processing workflows

        Example request body:
    ```json
        [
            {
                "main_db_id": 123,
                "application_step": "Decking",
                "user_name": "decker001",
                "application_status": "For Evaluation",
                "application_decision": "For Evaluation",
                "application_remarks": "Documents complete",
                "accomplished_date": "2025-01-19T14:30:00",
                "del_index": null,
                "del_previous": null,
                "del_last_index": null
            },
            {
                "main_db_id": 124,
                "application_step": "Decking",
                "user_name": "decker001",
                "application_status": "For Evaluation",
                "application_decision": "For Evaluation",
                "application_remarks": "All requirements met",
                "accomplished_date": "2025-01-19T14:30:00",
                "del_index": null,
                "del_previous": null,
                "del_last_index": null
            }
        ]
    ```

        Returns:
        - List of created log entries
        - Partial success: If some logs fail, returns only successful ones
    """
    if not logs_in:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No logs provided"
        )

    if len(logs_in) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create more than 100 logs at once",
        )

    created_logs = []
    errors = []

    for idx, log_in in enumerate(logs_in):
        try:
            log = crud_logs.create(db, log_in=log_in)
            created_logs.append(log)
        except Exception as e:
            errors.append(
                {"index": idx, "main_db_id": log_in.main_db_id, "error": str(e)}
            )

    # If all failed
    if not created_logs:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create all logs. Errors: {errors}",
        )

    # If some failed, log warning but return successful ones
    if errors:
        print(
            f"⚠️ Partial success: {len(created_logs)}/{len(logs_in)} logs created. Errors: {errors}"
        )

    return created_logs


@router.get("/main-db/{main_db_id}", response_model=List[ApplicationLogResponse])
def get_logs_by_main_db(
    main_db_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all logs for a specific application (main_db record)

    Returns logs ordered by created_at (newest first)
    """
    logs = crud_logs.get_by_main_db_id(db, main_db_id=main_db_id)
    return logs


@router.get(
    "/main-db/{main_db_id}/step/{step}", response_model=List[ApplicationLogResponse]
)
def get_logs_by_step(
    main_db_id: int,
    step: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get logs for a specific workflow step

    Common steps:
    - Decking
    - Evaluation
    - Checking
    - Supervisor
    - QA
    - Director
    - Releasing
    """
    logs = crud_logs.get_by_step(db, main_db_id=main_db_id, step=step)
    return logs


@router.get("/open-tasks", response_model=OpenTasksResponse)
def get_open_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=10000),
    search: Optional[str] = Query(None),
    application_step: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    dtn_date_from: Optional[str] = Query(
        None, description="YYYYMMDD, based on DTN digits 1-8"
    ),
    dtn_date_to: Optional[str] = Query(
        None, description="YYYYMMDD, based on DTN digits 1-8"
    ),
    date_received_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_received_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Task list for Reassignment/Reroute page and Directors Target.
    Filtered to del_last_index=1, del_thread='Open'.
    """
    return crud_logs.get_open_tasks(
        db,
        page=page,
        page_size=page_size,
        search=search,
        application_step=application_step,
        user_name=user_name,
        dtn_date_from=dtn_date_from,
        dtn_date_to=dtn_date_to,
        date_received_from=date_received_from,
        date_received_to=date_received_to,
    )


@router.get("/open-tasks/steps")
def get_open_task_steps(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Distinct application_step values among open tasks — for the filter dropdown."""
    return {"steps": crud_logs.get_distinct_steps(db)}


# ══════════════════════════════════════════════════════════════════════
#  NEW — Distinct user_name values among open tasks
#  GET /api/application-logs/open-tasks/users
# ══════════════════════════════════════════════════════════════════════
@router.get("/open-tasks/users")
def get_open_task_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Distinct user_name values among open tasks — for the Current User filter dropdown."""
    return {"users": crud_logs.get_distinct_users(db)}


@router.get("/{log_id}", response_model=ApplicationLogResponse)
def get_log(
    log_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a specific application log by ID"""
    log = crud_logs.get_by_id(db, log_id=log_id)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found",
        )

    return log


@router.put("/{log_id}", response_model=ApplicationLogResponse)
def update_log(
    log_id: int,
    log_in: ApplicationLogUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update an application log"""
    log = crud_logs.update(db, log_id=log_id, log_in=log_in)

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found",
        )

    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(
    log_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete an application log"""
    success = crud_logs.delete(db, log_id=log_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found",
        )

    return None


@router.get("/main-db/{main_db_id}/last-index")
def get_last_index(
    main_db_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get the latest del_index for an application.
    Returns 0 if no logs exist.
    """
    try:
        last_index = crud_logs.get_last_index(db, main_db_id)
        return {
            "main_db_id": main_db_id,
            "last_index": last_index,
            "next_index": last_index + 1,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch last index: {str(e)}"
        )


# ══════════════════════════════════════════════════════════════════════
#  NEW — Get logs by DTN (query param)
#  GET /api/application-logs?dtn=20210927134427
# ══════════════════════════════════════════════════════════════════════
@router.get("/", response_model=List[ApplicationLogResponse])
def get_logs_by_dtn(
    dtn: int = Query(..., description="Document Tracking Number (DB_DTN)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all application logs for a given DTN.

    1. Resolves DB_DTN → DB_ID from main_db
    2. Returns all application_logs rows for that main_db_id,
       ordered by del_index DESC then created_at DESC so the
       latest step is always shown first.

    Example:
        GET /api/application-logs?dtn=20210927134427
    """
    main_record = db.query(MainDB).filter(MainDB.DB_DTN == dtn).first()

    if not main_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No main_db record found for DTN {dtn}",
        )

    logs = (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.main_db_id == main_record.DB_ID)
        .order_by(ApplicationLogs.del_index.desc(), ApplicationLogs.created_at.desc())
        .all()
    )

    # Override displayed username with the live value from the users table
    for log in logs:
        log.user_name = log.user.username if log.user else None

    return logs


# ══════════════════════════════════════════════════════════════════════
#  Re-assignment endpoint
#  POST /api/application-logs/re-assign
# ══════════════════════════════════════════════════════════════════════
@router.post(
    "/re-assign",
    response_model=ApplicationLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def reassign_application(
    log_in: ApplicationLogCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        log = crud_logs.reassign(db, log_in=log_in)
        return log
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process re-assignment: {str(e)}",
        )


@router.post(
    "/re-route",
    response_model=ApplicationLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def reroute_application(
    log_in: ApplicationLogCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import text
    from datetime import datetime

    mysql_now = db.execute(text("SELECT NOW()")).fetchone()[0]

    received_at = log_in.rerouted_at

    python_now = datetime.now()

    print("=" * 50)
    print(f"MySQL NOW():     {mysql_now}")
    print(f"Python now():    {python_now}")
    print(f"Received rerouted_at: {received_at}")
    print(f"tzinfo: {received_at.tzinfo if received_at else None}")
    print("=" * 50)

    try:
        log = crud_logs.reroute(db, log_in=log_in)
        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{log_id}/star", response_model=ApplicationLogResponse)
def star_application_log(
    log_id: int,
    starred: bool = Query(..., description="true = star, false = unstar"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Toggle starred state of an application log."""
    log = toggle_star(db, log_id=log_id, star=starred)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application log with id {log_id} not found",
        )
    return log
