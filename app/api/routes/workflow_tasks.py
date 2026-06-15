"""
Router: ApplicationLogs + MainDB Joined View
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.crud.workflow_tasks import (
    get_logs_joined_with_main_db,
    get_logs_by_thread,
    mark_log_as_read,
    mark_logs_as_received,
    get_task_count_for_user,
)
from app.schemas.workflow_tasks import (
    LogWithMainDBListResponse,
    LogWithMainDBResponse,
    MarkReadResponse,
    MarkReceivedRequest,
    MarkReceivedBulkResponse,
    MarkReceivedItemResponse,
)
from typing import List

router = APIRouter(
    prefix="/api/workflow_tasks",
    tags=["Workflow Tasks"],
)


@router.get("/", response_model=LogWithMainDBListResponse)
def list_logs_with_main_db(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
    del_thread: Optional[str] = Query(None),
    del_last_index: Optional[int] = Query(None),
    only_latest_per_thread: bool = Query(False),
    application_step: Optional[str] = Query(None),
    application_status: Optional[str] = Query(None),
    application_decision: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    main_db_id: Optional[int] = Query(None),
    dtn: Optional[int] = Query(None),
    est_cat: Optional[str] = Query(None),
    app_type: Optional[str] = Query(None),
    db_app_status: Optional[str] = Query(None),
    lto_company: Optional[str] = Query(None),
    brand_name: Optional[str] = Query(None),
    generic_name: Optional[str] = Query(None),
    prescription: Optional[str] = Query(None),
    processing_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * page_size

    logs, total = get_logs_joined_with_main_db(
        db=db,
        skip=skip,
        limit=page_size,
        del_thread=del_thread,
        del_last_index=del_last_index,
        only_latest_per_thread=only_latest_per_thread,
        application_step=application_step,
        application_status=application_status,
        application_decision=application_decision,
        user_name=user_name,
        user_id=user_id, 
        main_db_id=main_db_id,
        dtn=dtn,
        est_cat=est_cat,
        app_type=app_type,
        db_app_status=db_app_status,
        lto_company=lto_company,
        brand_name=brand_name,
        generic_name=generic_name,
        prescription=prescription,
        processing_type=processing_type,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": logs,
    }


@router.patch("/{log_id}/mark-read", response_model=MarkReadResponse)
def mark_as_read(
    log_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Mark a single ApplicationLog as read.
    Sets is_read = 1 and read_at = now(). Idempotent.
    """
    log = mark_log_as_read(db=db, log_id=log_id)

    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    return {
        "id": log.id,
        "is_read": log.is_read,
        "read_at": log.read_at,
    }


@router.patch("/mark-received", response_model=MarkReceivedBulkResponse)
def mark_as_received(
    body: MarkReceivedRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Bulk mark ApplicationLogs as received.

    - Accepts a list of log IDs in the request body.
    - Idempotent: already-received rows are skipped gracefully.
    - Records who received them via the authenticated user's username.
    - Returns a summary of updated vs skipped counts plus per-row results.

    Request body:
        { "ids": [1, 2, 3] }

    Response:
        {
            "updated": 2,
            "skipped": 1,
            "results": [
                { "id": 1, "is_received": 1, "received_at": "...", "received_by": "jdoe" },
                ...
            ]
        }
    """
    updated_logs, updated_count, skipped_count = mark_logs_as_received(
        db=db,
        log_ids=body.ids,
        received_by=current_user.username,
    )

    results = [
        MarkReceivedItemResponse(
            id=log.id,
            is_received=log.is_received,
            received_at=log.received_at,
            received_by=log.received_by,
        )
        for log in updated_logs
    ]

    return MarkReceivedBulkResponse(
        updated=updated_count,
        skipped=skipped_count,
        results=results,
    )


@router.get("/thread/{del_thread}", response_model=LogWithMainDBListResponse)
def get_thread_history(
    del_thread: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get the full audit trail of a specific del_thread.
    Returns all logs ordered by del_index ascending.
    """
    skip = (page - 1) * page_size
    logs, total = get_logs_by_thread(db=db, del_thread=del_thread, skip=skip, limit=page_size)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": logs,
    }

@router.get("/my-task-count")
def get_my_task_count(
    application_status: Optional[str] = Query("IN PROGRESS"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = get_task_count_for_user(
        db=db,
        user_id=current_user.id,
        application_status=application_status,
    )
    return {"count": count}