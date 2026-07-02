# app/api/routes/closed_tasks.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.main_db import MainDB

import app.crud.closed_tasks as crud_closed
from app.schemas.closed_tasks import (
    ClosedTaskCreate,
    ClosedTaskBulkCreate,
    ClosedTaskResponse,
    ClosedTaskListResponse,
)

router = APIRouter(
    prefix="/api/closed-tasks",
    tags=["Closed Tasks"],
)


# ══════════════════════════════════════════════════════════════════════
#  POST /api/closed-tasks/
# ══════════════════════════════════════════════════════════════════════
@router.post(
    "/",
    response_model=ClosedTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Permanently close a single task",
)
def close_task(
    task_in      : ClosedTaskCreate,
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    if crud_closed.is_already_closed(db, task_in.main_db_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"main_db_id {task_in.main_db_id} has already been permanently closed.",
        )

    if not db.query(MainDB).filter(MainDB.DB_ID == task_in.main_db_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No main_db record found for id {task_in.main_db_id}.",
        )

    try:
        return crud_closed.create(db, task_in=task_in)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close task: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════
#  POST /api/closed-tasks/bulk
# ══════════════════════════════════════════════════════════════════════
@router.post(
    "/bulk",
    response_model=List[ClosedTaskResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Permanently close multiple tasks at once",
)
def close_tasks_bulk(
    bulk_in      : ClosedTaskBulkCreate,
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    if len(bulk_in.main_db_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot close more than 50 tasks at once.",
        )

    already_closed_ids = [
        mid for mid in bulk_in.main_db_ids
        if crud_closed.is_already_closed(db, mid)
    ]
    not_found_ids = [
        mid for mid in bulk_in.main_db_ids
        if not crud_closed.is_already_closed(db, mid)
        and not db.query(MainDB).filter(MainDB.DB_ID == mid).first()
    ]

    errors = {}
    if already_closed_ids:
        errors["already_closed"] = already_closed_ids
    if not_found_ids:
        errors["not_found"] = not_found_ids

    if errors:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Some tasks could not be closed.", "errors": errors},
        )

    try:
        return crud_closed.create_bulk(db, bulk_in=bulk_in)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close tasks: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/cpr-failed
#  Lahat ng tasks na nag-fail ang CPR Verification Portal insert
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/cpr-failed",
    response_model=ClosedTaskListResponse,
    summary="List closed tasks where CPR insert failed",
)
def list_cpr_failed(
    skip         : int  = Query(0,   ge=0),
    limit        : int  = Query(100, ge=1, le=500),
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    items = crud_closed.get_cpr_failed(db, skip=skip, limit=limit)
    return ClosedTaskListResponse(total=len(items), items=items)


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/cpr-skipped
#  Lahat ng tasks na sinadyang i-OFF ang CPR API bago mag-close
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/cpr-skipped",
    response_model=ClosedTaskListResponse,
    summary="List closed tasks where CPR insert was skipped (API OFF)",
)
def list_cpr_skipped(
    skip         : int  = Query(0,   ge=0),
    limit        : int  = Query(100, ge=1, le=500),
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    items = crud_closed.get_cpr_skipped(db, skip=skip, limit=limit)
    return ClosedTaskListResponse(total=len(items), items=items)


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/{closed_task_id}
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/{closed_task_id}",
    response_model=ClosedTaskResponse,
    summary="Get a closed-task record by ID",
)
def get_closed_task(
    closed_task_id : int,
    current_user   : User    = Depends(get_current_active_user),
    db             : Session = Depends(get_db),
):
    record = crud_closed.get_by_id(db, closed_task_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Closed-task record {closed_task_id} not found.",
        )
    return record


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/main-db/{main_db_id}
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/main-db/{main_db_id}",
    response_model=ClosedTaskResponse,
    summary="Get the closed-task record for a given main_db_id",
)
def get_closed_task_by_main_db(
    main_db_id   : int,
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    record = crud_closed.get_by_main_db_id(db, main_db_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No closed-task record found for main_db_id {main_db_id}.",
        )
    return record


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/check/{main_db_id}
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/check/{main_db_id}",
    summary="Check if an application is already permanently closed",
)
def check_is_closed(
    main_db_id   : int,
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    return {
        "main_db_id" : main_db_id,
        "is_closed"  : crud_closed.is_already_closed(db, main_db_id),
    }


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/",
    response_model=ClosedTaskListResponse,
    summary="List all permanently closed tasks (paginated)",
)
def list_closed_tasks(
    skip         : int  = Query(0,   ge=0),
    limit        : int  = Query(100, ge=1, le=500),
    current_user : User    = Depends(get_current_active_user),
    db           : Session = Depends(get_db),
):
    items = crud_closed.get_all(db, skip=skip, limit=limit)
    return ClosedTaskListResponse(total=len(items), items=items)