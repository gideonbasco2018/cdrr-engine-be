"""
CRUD: ApplicationLogs RIGHT JOIN MainDB
Optimized for table display filtered by del_thread / del_last_index

Key behavior:
- RIGHT JOIN from ApplicationLogs → MainDB (all logs returned, MainDB info attached)
- Filter by del_thread   → show only logs belonging to a specific thread
- Filter by del_last_index → show only the "latest" log per thread (current state)
- Both filters can be combined
"""
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import func, desc, or_, and_
from typing import Optional, List, Tuple

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB


def get_logs_joined_with_main_db(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    # ─── del_thread / del_last_index filters (primary use case) ───
    del_thread: Optional[str] = None,           # filter by specific thread
    del_last_index: Optional[int] = None,        # filter by specific last index value
    only_latest_per_thread: bool = False,        # True = show only latest log per thread
    # ─── Log-level filters ───────────────────────────────────────
    application_step: Optional[str] = None,
    application_status: Optional[str] = None,
    application_decision: Optional[str] = None,
    user_name: Optional[str] = None,
    main_db_id: Optional[int] = None,
    # ─── MainDB-level filters ────────────────────────────────────
    dtn: Optional[int] = None,
    est_cat: Optional[str] = None,
    app_type: Optional[str] = None,
    db_app_status: Optional[str] = None,
    lto_company: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    prescription: Optional[str] = None,
    processing_type: Optional[str] = None,
    # ─── Search ──────────────────────────────────────────────────
    search: Optional[str] = None,
    # ─── Sort ────────────────────────────────────────────────────
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[ApplicationLogs], int]:
    """
    Fetch ApplicationLogs with MainDB info (RIGHT JOIN semantics via outerjoin).

    Filter Options:
    - del_thread          : Get all logs belonging to a specific thread UUID/string
    - del_last_index      : Get logs where del_last_index matches a value
    - only_latest_per_thread : Subquery to return only the row with max del_index per thread

    Returns:
        (list of ApplicationLogs with .main_db loaded, total count)
    """

    # ─── Base query: outerjoin from ApplicationLogs → MainDB ─────
    # This is RIGHT JOIN semantics: all logs returned even if MainDB is missing
    query = (
        db.query(ApplicationLogs)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(contains_eager(ApplicationLogs.main_db))
    )

    # ─── only_latest_per_thread ───────────────────────────────────
    # Subquery: for each (main_db_id, del_thread), get the max del_index
    # Then join back to get only those rows
    if only_latest_per_thread:
        latest_subq = (
            db.query(
                ApplicationLogs.main_db_id,
                ApplicationLogs.del_thread,
                func.max(ApplicationLogs.del_index).label("max_del_index"),
            )
            .filter(ApplicationLogs.del_thread.isnot(None))
            .group_by(ApplicationLogs.main_db_id, ApplicationLogs.del_thread)
            .subquery()
        )
        query = query.join(
            latest_subq,
            and_(
                ApplicationLogs.main_db_id == latest_subq.c.main_db_id,
                ApplicationLogs.del_thread == latest_subq.c.del_thread,
                ApplicationLogs.del_index == latest_subq.c.max_del_index,
            ),
        )

    # ─── del_thread filter ────────────────────────────────────────
    if del_thread is not None:
        query = query.filter(ApplicationLogs.del_thread == del_thread)

    # ─── del_last_index filter ────────────────────────────────────
    if del_last_index is not None:
        query = query.filter(ApplicationLogs.del_last_index == del_last_index)

    # ─── Log-level filters ────────────────────────────────────────
    if main_db_id is not None:
        query = query.filter(ApplicationLogs.main_db_id == main_db_id)

    if application_step:
        query = query.filter(ApplicationLogs.application_step == application_step)

    if application_status:
        query = query.filter(ApplicationLogs.application_status == application_status)

    if application_decision:
        query = query.filter(ApplicationLogs.application_decision == application_decision)

    if user_name:
        query = query.filter(ApplicationLogs.user_name == user_name)

    # ─── MainDB-level filters ─────────────────────────────────────
    if dtn is not None:
        query = query.filter(MainDB.DB_DTN == dtn)

    if est_cat:
        query = query.filter(MainDB.DB_EST_CAT == est_cat)

    if app_type:
        if app_type == "__EMPTY__":
            query = query.filter(or_(MainDB.DB_APP_TYPE.is_(None), MainDB.DB_APP_TYPE == ""))
        else:
            query = query.filter(MainDB.DB_APP_TYPE == app_type)

    if db_app_status:
        if db_app_status == "__EMPTY__":
            query = query.filter(or_(MainDB.DB_APP_STATUS.is_(None), MainDB.DB_APP_STATUS == ""))
        else:
            query = query.filter(MainDB.DB_APP_STATUS == db_app_status)

    if lto_company:
        query = query.filter(MainDB.DB_EST_LTO_COMP.like(f"%{lto_company}%"))

    if brand_name:
        query = query.filter(MainDB.DB_PROD_BR_NAME.like(f"%{brand_name}%"))

    if generic_name:
        query = query.filter(MainDB.DB_PROD_GEN_NAME.like(f"%{generic_name}%"))

    if prescription:
        if prescription == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_PROD_CLASS_PRESCRIP.is_(None), MainDB.DB_PROD_CLASS_PRESCRIP == "")
            )
        else:
            query = query.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)

    if processing_type:
        if processing_type == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_PROCESSING_TYPE.is_(None), MainDB.DB_PROCESSING_TYPE == "")
            )
        else:
            query = query.filter(MainDB.DB_PROCESSING_TYPE == processing_type)

    # ─── Global search ────────────────────────────────────────────
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                ApplicationLogs.application_step.like(pattern),
                ApplicationLogs.application_status.like(pattern),
                ApplicationLogs.user_name.like(pattern),
                ApplicationLogs.del_thread.like(pattern),
                MainDB.DB_EST_LTO_COMP.like(pattern),
                MainDB.DB_PROD_BR_NAME.like(pattern),
                MainDB.DB_PROD_GEN_NAME.like(pattern),
                MainDB.DB_REG_NO.like(pattern),
            )
        )

    # ─── Total count (before pagination) ─────────────────────────
    total = query.count()

    # ─── Sorting ──────────────────────────────────────────────────
    LOG_SORT_FIELDS = {
        "created_at", "updated_at", "accomplished_date", "start_date",
        "del_index", "del_last_index", "application_step",
        "application_status", "user_name",
    }
    MAIN_DB_SORT_FIELDS = {
        "DB_DATE_EXCEL_UPLOAD", "DB_DTN", "DB_EST_LTO_COMP",
        "DB_PROD_BR_NAME", "DB_APP_STATUS",
    }

    if sort_by in LOG_SORT_FIELDS and hasattr(ApplicationLogs, sort_by):
        col = getattr(ApplicationLogs, sort_by)
        query = query.order_by(desc(col) if sort_order == "desc" else col)
    elif sort_by in MAIN_DB_SORT_FIELDS and hasattr(MainDB, sort_by):
        col = getattr(MainDB, sort_by)
        query = query.order_by(desc(col) if sort_order == "desc" else col)
    else:
        query = query.order_by(desc(ApplicationLogs.created_at))

    # ─── Pagination ───────────────────────────────────────────────
    logs = query.offset(skip).limit(limit).all()

    return logs, total


def get_logs_by_thread(
    db: Session,
    del_thread: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[ApplicationLogs], int]:
    """
    Get ALL logs belonging to a specific del_thread, ordered by del_index asc.
    Useful for showing the full history of a thread (audit trail view).
    """
    query = (
        db.query(ApplicationLogs)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(contains_eager(ApplicationLogs.main_db))
        .filter(ApplicationLogs.del_thread == del_thread)
        .order_by(ApplicationLogs.del_index.asc())
    )

    total = query.count()
    logs = query.offset(skip).limit(limit).all()
    return logs, total