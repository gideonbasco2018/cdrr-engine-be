"""
CRUD: ApplicationLogs RIGHT JOIN MainDB
"""

from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import func, desc, or_, and_
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta

PHT = timezone(timedelta(hours=8))

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB
from app.models.user import User
from app.models.target_assignment import TargetAssignment


def get_logs_joined_with_main_db(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    del_thread: Optional[str] = None,
    del_last_index: Optional[int] = None,
    only_latest_per_thread: bool = False,
    application_step: Optional[str] = None,
    application_status: Optional[str] = None,
    application_decision: Optional[str] = None,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
    main_db_id: Optional[int] = None,
    dtn: Optional[str] = None,
    est_cat: Optional[str] = None,
    app_type: Optional[str] = None,
    db_app_status: Optional[str] = None,
    lto_company: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    prescription: Optional[str] = None,
    processing_type: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[ApplicationLogs], int]:

    query = (
        db.query(ApplicationLogs)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(contains_eager(ApplicationLogs.main_db))
    )

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

    if del_thread is not None:
        query = query.filter(ApplicationLogs.del_thread == del_thread)
    if del_last_index is not None:
        query = query.filter(ApplicationLogs.del_last_index == del_last_index)
    if main_db_id is not None:
        query = query.filter(ApplicationLogs.main_db_id == main_db_id)
    if application_step:
        query = query.filter(ApplicationLogs.application_step == application_step)
    if application_status:
        query = query.filter(ApplicationLogs.application_status == application_status)
    if application_decision:
        query = query.filter(
            ApplicationLogs.application_decision == application_decision
        )
    if user_name:
        query = query.filter(ApplicationLogs.user_name == user_name)
    if user_id is not None:
        query = query.filter(ApplicationLogs.user_id == user_id)
    if dtn:
        query = query.filter(
            or_(
                MainDB.DB_DTN == int(dtn),
                MainDB.DB_OLD_RSN == dtn,
            )
        )
    if est_cat:
        query = query.filter(MainDB.DB_EST_CAT == est_cat)
    if app_type:
        if app_type == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_APP_TYPE.is_(None), MainDB.DB_APP_TYPE == "")
            )
        else:
            query = query.filter(MainDB.DB_APP_TYPE == app_type)
    if db_app_status:
        if db_app_status == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_APP_STATUS.is_(None), MainDB.DB_APP_STATUS == "")
            )
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
                or_(
                    MainDB.DB_PROD_CLASS_PRESCRIP.is_(None),
                    MainDB.DB_PROD_CLASS_PRESCRIP == "",
                )
            )
        else:
            query = query.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    if processing_type:
        if processing_type == "__EMPTY__":
            query = query.filter(
                or_(
                    MainDB.DB_PROCESSING_TYPE.is_(None), MainDB.DB_PROCESSING_TYPE == ""
                )
            )
        else:
            query = query.filter(MainDB.DB_PROCESSING_TYPE == processing_type)
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

    total = query.count()

    LOG_SORT_FIELDS = {
        "created_at",
        "updated_at",
        "accomplished_date",
        "start_date",
        "del_index",
        "del_last_index",
        "application_step",
        "application_status",
        "user_name",
    }
    MAIN_DB_SORT_FIELDS = {
        "DB_DATE_EXCEL_UPLOAD",
        "DB_DTN",
        "DB_EST_LTO_COMP",
        "DB_PROD_BR_NAME",
        "DB_APP_STATUS",
    }

    # A secondary sort key on the primary key is required — without it, rows
    # that tie on the primary sort column (e.g. many logs sharing the same
    # created_at) come back in a non-deterministic order on every request,
    # which made "select all" + generate transmittal look randomized.
    if sort_by in LOG_SORT_FIELDS and hasattr(ApplicationLogs, sort_by):
        col = getattr(ApplicationLogs, sort_by)
        query = query.order_by(
            desc(col) if sort_order == "desc" else col, ApplicationLogs.id
        )
    elif sort_by in MAIN_DB_SORT_FIELDS and hasattr(MainDB, sort_by):
        col = getattr(MainDB, sort_by)
        query = query.order_by(
            desc(col) if sort_order == "desc" else col, ApplicationLogs.id
        )
    else:
        query = query.order_by(desc(ApplicationLogs.created_at), ApplicationLogs.id)

    logs = query.offset(skip).limit(limit).all()

    # ── Attach del_previous log data (sent_by) ────────────────────────────────
    # For each log, fetch the previous step's log entry (del_index == del_previous)
    # in a single bulk query — no N+1.
    #
    # These 3 attributes are picked up by LogWithMainDBResponse via orm_mode:
    #   log.sent_by_user_name  → "Sent By" column
    #   log.sent_by_user_id    → user_id of the sender
    #   log.sent_at            → "Last Modified" column (when it was forwarded)
    _attach_sent_by(db, logs)
    _attach_target_info(db, logs)
    # ─────────────────────────────────────────────────────────────────────────

    return logs, total


def _attach_sent_by(db: Session, logs: List[ApplicationLogs]) -> None:
    """
    Bulk-fetch the previous log entry for each log (where del_index == del_previous)
    and attach sent_by_user_name, sent_by_user_id, sent_at as Python attributes.

    Uses a single DB query regardless of how many logs are passed.
    Logs with no del_previous (first step) receive None for all three fields.
    """
    # Build (main_db_id, del_previous) pairs for logs that have a previous step
    pairs = [
        (log.main_db_id, log.del_previous)
        for log in logs
        if log.del_previous is not None
    ]

    prev_lookup: dict = {}

    if pairs:
        conditions = [
            and_(
                ApplicationLogs.main_db_id == mid,
                ApplicationLogs.del_index == didx,
            )
            for mid, didx in pairs
        ]
        prev_logs = db.query(ApplicationLogs).filter(or_(*conditions)).all()
        prev_lookup = {(row.main_db_id, row.del_index): row for row in prev_logs}

    # Collect all sent_by_user_ids to bulk-fetch user info
    user_ids = set()
    for log in logs:
        prev = prev_lookup.get((log.main_db_id, log.del_previous))
        if prev and prev.user_id:
            user_ids.add(prev.user_id)

    # Single bulk query for all relevant users
    user_lookup: dict = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_lookup = {u.id: u for u in users}

    # Attach attributes
    for log in logs:
        prev = prev_lookup.get((log.main_db_id, log.del_previous))
        log.sent_by_user_name = prev.user_name if prev else None
        log.sent_by_user_id = prev.user_id if prev else None
        log.sent_at = prev.updated_at if prev else None

        # NEW: resolve first_name + surname from sent_by_user_id
        sender = user_lookup.get(prev.user_id) if prev and prev.user_id else None
        log.sent_by_first_name = sender.first_name if sender else None
        log.sent_by_surname = sender.surname if sender else None

        log.prev_del_index = prev.del_index if prev else None
        log.prev_application_step = prev.application_step if prev else None
        log.prev_application_status = prev.application_status if prev else None
        log.prev_application_decision = prev.application_decision if prev else None
        log.prev_application_remarks = prev.application_remarks if prev else None
        log.prev_action_type = prev.action_type if prev else None
        log.prev_decision_result = prev.decision_result if prev else None
        log.prev_decision_authority = prev.decision_authority_name if prev else None
        log.prev_accomplished_date = prev.accomplished_date if prev else None
        log.prev_start_date = prev.start_date if prev else None
        log.prev_deadline_date = prev.deadline_date if prev else None


# ── unchanged functions below ─────────────────────────────────────────────────
def _attach_target_info(db: Session, logs: List[ApplicationLogs]) -> None:
    """
    Bulk-fetch active TargetAssignment rows for the given logs and attach
    is_targeted / target_start_date / target_end_date / target_remarks
    as Python attributes — same pattern as _attach_sent_by, no N+1.
    """
    log_ids = [log.id for log in logs]
    if not log_ids:
        return

    targets = (
        db.query(TargetAssignment)
        .filter(
            TargetAssignment.application_log_id.in_(log_ids),
            TargetAssignment.is_active == True,  # noqa: E712
        )
        .all()
    )
    target_lookup = {t.application_log_id: t for t in targets}

    for log in logs:
        t = target_lookup.get(log.id)
        log.is_targeted = t is not None
        log.target_start_date = t.target_start_date if t else None
        log.target_end_date = t.target_end_date if t else None
        log.target_remarks = t.remarks if t else None


def get_logs_by_thread(
    db: Session,
    del_thread: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[ApplicationLogs], int]:
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


def mark_log_as_read(
    db: Session,
    log_id: int,
) -> Optional[ApplicationLogs]:
    log = db.query(ApplicationLogs).filter(ApplicationLogs.id == log_id).first()
    if not log:
        return None
    if not log.is_read:
        log.is_read = 1
        log.read_at = datetime.now(PHT).replace(tzinfo=None)
        db.commit()
        db.refresh(log)
    return log


def mark_logs_as_received(
    db: Session,
    log_ids: List[int],
    received_by: str,
) -> Tuple[List[ApplicationLogs], int, int]:
    logs = db.query(ApplicationLogs).filter(ApplicationLogs.id.in_(log_ids)).all()
    now_pht = datetime.now(PHT).replace(tzinfo=None)
    updated: List[ApplicationLogs] = []
    skipped = 0
    for log in logs:
        if log.is_received:
            skipped += 1
        else:
            log.is_received = 1
            log.received_at = now_pht
            log.received_by = received_by
            updated.append(log)
    if updated:
        db.commit()
        for log in updated:
            db.refresh(log)
    return updated, len(updated), skipped


def get_task_count_for_user(
    db: Session,
    user_id: int,
    application_status: Optional[str] = "IN PROGRESS",
) -> int:
    """
    Returns the count of active tasks assigned to a specific user.
    Equivalent to:
      SELECT count(*) FROM application_logs
      WHERE application_status='IN PROGRESS'
        AND del_last_index='1'
        AND del_thread='Open'
        AND user_id=<user_id>
    """
    count = (
        db.query(func.count(ApplicationLogs.id))
        .filter(ApplicationLogs.user_id == user_id)
        .filter(ApplicationLogs.application_status == application_status)
        .filter(ApplicationLogs.del_last_index == "1")
        .filter(ApplicationLogs.del_thread == "Open")
        .scalar()
    )

    return count or 0
