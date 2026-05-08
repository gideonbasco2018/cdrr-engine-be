# app/api/routes/closed_tasks.py
"""
Closed Tasks Routes
Permanently close workflow tasks — this action cannot be undone.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

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
#  Permanently close a SINGLE task
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
    """
    Permanently close one task.

    - Marks the active `application_logs` row for that `main_db_id` as COMPLETED.
    - Inserts an audit record into `closed_tasks`.
    - **This action cannot be undone.**

    The `closed_by_user_id` and `closed_by_user_name` in the request body
    should match the currently authenticated user. The route does NOT
    override them so that the frontend can pass the exact user object it
    already has without an extra lookup.
    """
    # Guard: already closed?
    if crud_closed.is_already_closed(db, task_in.main_db_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"main_db_id {task_in.main_db_id} has already been permanently closed.",
        )

    # Guard: main_db record exists?
    main_record = db.query(MainDB).filter(MainDB.DB_ID == task_in.main_db_id).first()
    if not main_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No main_db record found for id {task_in.main_db_id}.",
        )

    try:
        closed = crud_closed.create(db, task_in=task_in)
        return closed
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close task: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════
#  POST /api/closed-tasks/bulk
#  Permanently close MULTIPLE tasks in one action
#  (matches the "1 record selected" UI — but also handles N > 1)
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
    """
    Permanently close one or more tasks in a single request.

    - Max 50 tasks per call.
    - All-or-nothing: if any record fails the pre-checks, the whole
      batch is rejected before anything is written.
    - **This action cannot be undone.**

    Example request body:
    ```json
    {
        "main_db_ids": [101, 102, 103],
        "reason_for_closing": "Task fully completed",
        "remarks": "Verified by supervisor",
        "closed_by_user_id": 7,
        "closed_by_user_name": "jdelacruz"
    }
    ```
    """
    if len(bulk_in.main_db_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot close more than 50 tasks at once.",
        )

    # Pre-flight checks for each id
    already_closed_ids = []
    not_found_ids      = []

    for mid in bulk_in.main_db_ids:
        if crud_closed.is_already_closed(db, mid):
            already_closed_ids.append(mid)
        elif not db.query(MainDB).filter(MainDB.DB_ID == mid).first():
            not_found_ids.append(mid)

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
        closed_list = crud_closed.create_bulk(db, bulk_in=bulk_in)
        return closed_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close tasks: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/{closed_task_id}
#  Fetch a specific closed-task audit record by its own PK
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
#  Check / retrieve the closed-task record for a specific application
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
#  Simple boolean check — is this application already permanently closed?
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
    """
    Returns `{ "main_db_id": X, "is_closed": true/false }`.
    Use this on the frontend before showing the Close Task modal.
    """
    return {
        "main_db_id": main_db_id,
        "is_closed" : crud_closed.is_already_closed(db, main_db_id),
    }


# ══════════════════════════════════════════════════════════════════════
#  GET /api/closed-tasks/
#  List all closed tasks (paginated)
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