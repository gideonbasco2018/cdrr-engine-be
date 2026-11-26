# app/api/routes/gmp_closed_tasks.py
"""FGMP "Close Task (Final)" — see app/crud/gmp_closed_tasks.py."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.crud import gmp_closed_tasks as crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.gmp_closed_task import (
    GMPCloseTasksRequest,
    GMPCloseTasksResponse,
    GMPClosedTaskResponse,
)
# Same Google Docs worksheet clean-up every other "application moved" action does.
from app.api.routes.gmp_record import _queue_worksheet_access_removal

router = APIRouter(
    prefix="/api/gmp-closed-tasks",
    tags=["GMP Closed Tasks"],
    dependencies=[Depends(get_current_active_user)],
)


@router.post(
    "/bulk",
    response_model=GMPCloseTasksResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Permanently close FGMP applications (every reference of each DTN)",
)
def close_tasks_bulk(
    req: GMPCloseTasksRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if len(req.record_ids) > crud.MAX_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot close more than {crud.MAX_PER_BATCH} applications at once.",
        )
    try:
        results, total_logs, first_ids = crud.close_dtns(
            db, req, user_id=current_user.id, user_name=current_user.username
        )
    except crud.CloseBlocked as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": e.message, "errors": e.errors},
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close applications: {e}",
        )

    # The application is finished: clear edit/comment access on its worksheets.
    for rid in first_ids:
        _queue_worksheet_access_removal(background_tasks, db, rid)

    return {
        "closed": results,
        "total_dtns": len(results),
        "total_references": sum(len(r["reference_nos"]) for r in results),
        "total_logs_closed": total_logs,
    }


@router.get(
    "/record/{record_id}",
    response_model=GMPClosedTaskResponse,
    summary="The close record of one reference, if it was closed",
)
def get_closed_by_record(record_id: int, db: Session = Depends(get_db)):
    row = crud.get_closed_by_record_id(db, record_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not closed.")
    return row
