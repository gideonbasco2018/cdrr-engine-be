"""
Router: ApplicationLogs + MainDB Joined View
Endpoints for table display filtered by del_thread / del_last_index
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.crud.workflow_tasks import get_logs_joined_with_main_db, get_logs_by_thread
from app.schemas.workflow_tasks import LogWithMainDBListResponse, LogWithMainDBResponse
from typing import List

router = APIRouter(
    prefix="/api/workflow_tasks",
    tags=["Workflow Tasks"],
)


@router.get("/", response_model=LogWithMainDBListResponse)
def list_logs_with_main_db(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),

    # ── del_thread / del_last_index ──────────────────────────────
    del_thread: Optional[str] = Query(None, description="Filter by specific thread ID"),
    del_last_index: Optional[int] = Query(None, description="Filter by del_last_index value"),
    only_latest_per_thread: bool = Query(
        False,
        description=(
            "If true, returns only the latest log entry per thread "
            "(max del_index per main_db_id + del_thread group). "
            "Ideal for table views showing current state."
        ),
    ),

    # ── Log-level filters ─────────────────────────────────────────
    application_step: Optional[str] = Query(None, description="e.g. Decking, Evaluation, Checking"),
    application_status: Optional[str] = Query(None),
    application_decision: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None, description="Username who performed the step"),
    main_db_id: Optional[int] = Query(None, description="Filter by specific MainDB record ID"),

    # ── MainDB-level filters ──────────────────────────────────────
    dtn: Optional[int] = Query(None, description="Filter by Document Tracking Number"),
    est_cat: Optional[str] = Query(None, description="Establishment Category"),
    app_type: Optional[str] = Query(None, description="Application Type. Use __EMPTY__ for null/empty."),
    db_app_status: Optional[str] = Query(None, description="MainDB Application Status. Use __EMPTY__ for null/empty."),
    lto_company: Optional[str] = Query(None),
    brand_name: Optional[str] = Query(None),
    generic_name: Optional[str] = Query(None),
    prescription: Optional[str] = Query(None, description="Use __EMPTY__ for null/empty."),
    processing_type: Optional[str] = Query(None, description="Processing Type. Use __EMPTY__ for null/empty."),

    # ── Search & Sort ─────────────────────────────────────────────
    search: Optional[str] = Query(None, description="Global search across log and MainDB fields"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),

    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    List ApplicationLogs joined with MainDB info, with flexible filtering.

    ### Common Use Cases:

    **Show current state of all threads (latest log per thread):**
    ```
    GET /api/logs-view/?only_latest_per_thread=true
    ```

    **Show all logs for a specific thread (audit trail):**
    ```
    GET /api/logs-view/?del_thread=abc-123-xyz
    ```

    **Show latest log per thread for a specific application:**
    ```
    GET /api/logs-view/?main_db_id=42&only_latest_per_thread=true
    ```

    **Show all logs at a specific del_last_index level:**
    ```
    GET /api/logs-view/?del_last_index=3
    ```
    """
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


@router.get("/thread/{del_thread}", response_model=LogWithMainDBListResponse)
def get_thread_history(
    del_thread: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get the full audit trail / history of a specific del_thread.
    Returns all logs for that thread ordered by del_index ascending.

    Useful for a "View History" modal/drawer on a table row.
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