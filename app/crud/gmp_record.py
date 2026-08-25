# app/crud/gmp_record.py
"""CRUD for GMPRecord — list, create, update, delete, audit logging, summaries."""
import uuid
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, or_, and_, case, cast, String, nullslast
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timezone, timedelta
from app.models.gmp_record import GMPRecord, GMPDelegation, GMPApplicationLogs, GMPFieldAuditLog
from app.schemas.gmp_record import GMPRecordCreate, GMPRecordUpdate
from app.crud.notification import create_notification, already_notified_today
from app.schemas.notification import NotificationCreate

# A record's GMP_APP_STATUS can be stale/blank while it's actively moving
# through the workflow — the reliable "still in progress" signal is an open
# (non-terminal) current_step. Mirrors getEffectiveStatus() in
# QueueTable.jsx / getEffectiveStatusWM() in WorkflowModal.jsx EXACTLY — this
# is the server-side port of that same logic, so the "Application Status"
# sidebar/filter agrees with what the table actually displays instead of
# grouping by the raw (frequently-null) column.
GMP_TERMINAL_STATUSES = ["COMPLETED", "RELEASED", "DISAPPROVED", "CANCELLED APPLICATION", "CANCELLED"]


def _effective_status_col():
    has_current_step = and_(GMPRecord.GMP_CURRENT_STEP.isnot(None), GMPRecord.GMP_CURRENT_STEP != "")
    return case(
        (func.upper(GMPRecord.GMP_APP_STATUS).in_(GMP_TERMINAL_STATUSES), GMPRecord.GMP_APP_STATUS),
        (has_current_step, "IN PROGRESS"),
        else_=GMPRecord.GMP_APP_STATUS,
    )

# The app server runs its OS clock in UTC (see docker-compose TZ: UTC) but
# GMP_DATE_EXCEL_UPLOAD / GMP_TRASH_DATE_ENCODED are DATETIME columns storing
# literal (non-timezone-aware) wall-clock time, and the DB session, other GMP
# CRUD modules (gmp_logs.py, application_logs.py, etc.), and the frontend all
# assume that literal value is Philippine Time — so plain datetime.now() here
# stored the wrong (UTC) wall-clock time and showed up ~8 hours off.
_PHT = timezone(timedelta(hours=8))


def _now() -> datetime:
    """Current time in Philippine Standard Time, timezone-naive for DB storage."""
    return datetime.now(_PHT).replace(tzinfo=None)

# ── Workflow steps ────────────────────────────────────────────────────────────
# Labels MUST match the `id` fields in src/components/gmp/shared/constants.js
# Group IDs: Decking=30, Evaluator=31, Checker=32, QA Admin=34,
#            LRD Chief Admin=17, OD Receiving=18, OD Releasing=19
# NOTE: The "QA Supervisor" step/group has been removed. Evaluator now routes
# directly to QA Admin. del_index values are used for GMPApplicationLogs
# bookkeeping only — they no longer imply a fixed traversal order (see
# GMP_ACTION_ROUTES below for actual routing).
GMP_LOG_STEPS = [
    ("Decking",         1),
    ("Evaluator",       2),
    ("Checker",         3),
    ("QA Admin",        4),
    ("LRD Chief Admin", 5),
    ("OD Receiving",    6),
    ("OD Releasing",    7),
    ("FROO",            8),
]

GMP_STEP_DEL_INDEX: Dict[str, int] = {label: idx for label, idx in GMP_LOG_STEPS}

# FROO's step label (group id 37) and the action it takes to hand the NFI back
# to the Evaluator. OD Releasing no longer routes new records here (the
# workflow now always ends at OD Releasing — see resolve_next_step below);
# this route entry is kept only so records already mid-detour (an open or
# completed FROO log from before this change) can still be advanced back to
# the Evaluator and finish out normally instead of getting stuck.
GMP_FROO_STEP = "FROO"
GMP_FROO_ACTION = "Forwarded to CDRR FGMP"

# ── Explicit action → next-step routing table ─────────────────────────────────
# Keyed by (current_step, action) exactly as sent from the frontend
# (WorkflowModal.jsx / GMPDeckModal.jsx / BulkDeckModal.jsx). A value of None
# means the action terminates the workflow — the current log completes and no
# new log is opened (e.g. Hold, Disapprove, Certificate Released).
#
# This table is the single source of truth for routing. It replaced purely
# positional "advance to whatever's next in GMP_LOG_STEPS" logic, which could
# not express:
#   - the Evaluator ⇄ Checker loop (Checker → Evaluator is a backward route)
#   - Evaluator → QA Admin (skips Checker entirely, for the "printed, for
#     signature" path)
#   - "Return to X" actions on QA Admin / LRD Chief Admin / OD Receiving /
#     OD Releasing, which all route backward relative to list order
#
# If you add a new Action option in the frontend, you MUST add a matching
# entry here or advance-step will reject it with a 400 (see the route handler).
GMP_ACTION_ROUTES: Dict[tuple, Optional[str]] = {
    ("Decking", "Forwarded to Evaluator"):        "Evaluator",
    ("Decking", "Disapprove"):                    None,

    ("Evaluator", "Endorsed to Checker"):         "Checker",
    ("Evaluator", "Endorsed to QA Admin"):        "QA Admin",
    # "For Compliance" self-loops back to Evaluator: the current log closes
    # as COMPLETED (visible in Application Logs, del_index auto-increments)
    # and a fresh IN PROGRESS log opens for the same evaluator — the task
    # stays on their queue, but now with a logged history trail.
    ("Evaluator", "For Compliance"):              "Evaluator",

    ("Checker", "Endorsed to Evaluator"):         "Evaluator",

    ("QA Admin", "Endorsed to LRD Chief Admin"):  "LRD Chief Admin",
    ("QA Admin", "Return to Evaluator"):          "Evaluator",
    ("QA Admin", "Disapprove"):                   None,

    ("LRD Chief Admin", "Forwarded to OD Receiving"): "OD Receiving",
    ("LRD Chief Admin", "Return to QA Admin"):        "QA Admin",
    ("LRD Chief Admin", "Disapprove"):                None,

    ("OD Receiving", "Endorsed to OD - Releasing"):   "OD Releasing",
    ("OD Receiving", "Return to LRD Chief Admin"):    "LRD Chief Admin",

    # OD Releasing is now always the end of the workflow, for every issuance
    # type — it used to redirect NFI issuance types on to FROO instead of
    # terminating (see resolve_next_step() below); that detour has been
    # removed.
    ("OD Releasing", "Scanned, Stamped and Forwarded to AFO Records"): None,

    # Kept only so records already mid-FROO-detour (opened before this change
    # removed the redirect) can still be advanced back to the Evaluator and
    # finish out normally instead of getting stuck.
    (GMP_FROO_STEP, GMP_FROO_ACTION): "Evaluator",
}


def resolve_next_step(current_step: str, action: str) -> Tuple[bool, Optional[str]]:
    """Returns (is_valid_route, next_step_label)."""
    route_key = (current_step, action)
    if route_key not in GMP_ACTION_ROUTES:
        return False, None
    return True, GMP_ACTION_ROUTES[route_key]

GMP_AUDIT_EXCLUDED_FIELDS = {
    "GMP_ID", "GMP_DATE_EXCEL_UPLOAD", "GMP_TRASH_DATE_ENCODED", "GMP_USER_UPLOADER",
}


def _get_field_label(field_name: str) -> str:
    try:
        col = GMPRecord.__table__.columns.get(field_name)
        if col is not None and col.comment:
            return col.comment
    except Exception:
        pass
    stripped = field_name[4:] if field_name.startswith("GMP_") else field_name
    return stripped.replace("_", " ").title()


def _normalize(value) -> str:
    if value is None or value == "":
        return "N/A"
    return str(value)


def _get_open_log(db: Session, gmp_record_id: int) -> Optional[GMPApplicationLogs]:
    return (
        db.query(GMPApplicationLogs)
        .filter(
            GMPApplicationLogs.gmp_record_id == gmp_record_id,
            GMPApplicationLogs.del_thread == "Open",
        )
        .order_by(GMPApplicationLogs.del_index.desc())
        .first()
    )


def log_field_changes(
    db: Session,
    gmp_record_id: int,
    before: Dict,
    after: Dict,
    action_type: str = "UPDATE",
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> List[GMPFieldAuditLog]:
    changed = []
    for field_name, new_val in after.items():
        if field_name in GMP_AUDIT_EXCLUDED_FIELDS:
            continue
        old_val = before.get(field_name)
        if _normalize(old_val) == _normalize(new_val):
            continue
        changed.append((field_name, old_val, new_val))

    if not changed:
        return []

    session_id = str(uuid.uuid4())
    open_log = _get_open_log(db, gmp_record_id)
    gmp_log_id = open_log.id if open_log else None
    step_context = open_log.application_step if open_log else "Edit Record"

    rows = []
    for field_name, old_val, new_val in changed:
        row = GMPFieldAuditLog(
            gmp_record_id=gmp_record_id,
            field_name=field_name,
            field_label=_get_field_label(field_name),
            old_value=_normalize(old_val),
            new_value=_normalize(new_val),
            action_type=action_type,
            gmp_log_id=gmp_log_id,
            step_context=step_context,
            session_id=session_id,
            user_name=user_name,
            user_id=user_id,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def get_field_audit_logs(
    db: Session,
    gmp_record_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[GMPFieldAuditLog], int]:
    query = db.query(GMPFieldAuditLog).filter(
        GMPFieldAuditLog.gmp_record_id == gmp_record_id
    )
    total = query.count()
    logs = (
        query.order_by(GMPFieldAuditLog.created_at.desc(), GMPFieldAuditLog.id.desc())
        .offset(skip).limit(limit).all()
    )
    return logs, total


def get_field_audit_logs_by_session(
    db: Session, session_id: str
) -> List[GMPFieldAuditLog]:
    return (
        db.query(GMPFieldAuditLog)
        .filter(GMPFieldAuditLog.session_id == session_id)
        .order_by(GMPFieldAuditLog.id.asc())
        .all()
    )


# ── Decked subquery ───────────────────────────────────────────────────────────
def _decked_subquery(db: Session):
    return (
        db.query(GMPApplicationLogs.gmp_record_id)
        .filter(GMPApplicationLogs.application_step == "Decking")
        .subquery()
    )


# ── Single record ─────────────────────────────────────────────────────────────
def get_gmp_record(db: Session, record_id: int) -> Optional[GMPRecord]:
    return (
        db.query(GMPRecord)
        .options(joinedload(GMPRecord.gmp_delegation))
        .filter(GMPRecord.GMP_ID == record_id)
        .first()
    )


# ── List with filters ─────────────────────────────────────────────────────────
# ── Primary-only filter ────────────────────────────────────────────────────
# GMP_DTN is no longer unique — every "Add Issuance" duplicate shares its
# DTN with a primary ('-01') reference number but has no workflow of its
# own (see add_gmp_issuance). Listing surfaces (Queue, summary, filter
# counts) should therefore only ever show the primary reference per DTN;
# siblings are visible via the Reference Number tabs inside WorkflowModal,
# not as their own queue rows. Records with no GMP_REFERENCE_NO at all
# (shouldn't exist post-migration, but tolerated) are treated as primary too.
# (reopen_gmp_to_decking() reopens a record in place rather than creating a
# new reference number, so there's no other source of non-'-01' records that
# carry their own real workflow — this stays a simple suffix check.)
def _primary_only(query):
    return query.filter(
        or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01"))
    )


def get_gmp_records(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    filters: Optional[Dict] = None,
    sort_by: str = "GMP_DATE_EXCEL_UPLOAD",
    sort_order: str = "desc",
) -> Tuple[List[GMPRecord], int]:
    query = db.query(GMPRecord).filter(
        or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted")
    )

    if filters is None:
        filters = {}

    tab               = filters.get("tab")
    # "view" is the DTN-vs-reference-number toggle (GMPQueuePage's Main/All
    # buttons) — independent of "tab". "main" always lists one row per DTN
    # (the primary '-01' reference), regardless of tab, with every sibling's
    # reference no. + issuance type bulk-attached below as `all_issuances`.
    # "all" (default) keeps the existing per-tab behavior: "Not Yet Decked"/
    # "Decked" key off workflow state, which only the primary reference ever
    # carries, so those stay primary-only; "All Reports" intentionally lists
    # every reference number as its own row.
    view              = filters.get("view")
    if view == "main" or tab in ("decked", "not_yet_decked"):
        query = _primary_only(query)
    app_status        = filters.get("app_status")
    est_category      = filters.get("est_category")
    pics_nonpics      = filters.get("pics_nonpics")
    transaction_type  = filters.get("transaction_type")
    type_of_issuance  = filters.get("type_of_issuance")
    current_step      = filters.get("current_step")
    evaluator         = filters.get("evaluator")
    dtn               = filters.get("dtn")
    dtns              = filters.get("dtns")
    related_dtn       = filters.get("related_dtn")
    lto_company       = filters.get("lto_company")
    uploaded_by       = filters.get("uploaded_by")
    upload_date_from  = filters.get("upload_date_from")
    upload_date_to    = filters.get("upload_date_to")
    date_received_from = filters.get("date_received_from")
    date_received_to   = filters.get("date_received_to")

    # Extra per-column text filters — Advanced Filters modal fields that
    # aren't already covered by the sidebar quick filters or the fields
    # above. Each is a simple "contains" match on its GMPRecord column.
    TEXT_FIELD_COLUMNS = {
        "reference_no":                 GMPRecord.GMP_REFERENCE_NO,
        "lto_number":                   GMPRecord.GMP_LTO_NUMBER,
        "address":                      GMPRecord.GMP_LTO_ADDRESS,
        "foreign_manufacturer":         GMPRecord.GMP_FOREIGN_MANUFACTURER,
        "foreign_manufacturer_address": GMPRecord.GMP_FOREIGN_MANUFACTURER_ADDRESS,
        "secpa_number":                 GMPRecord.GMP_SECPA_NUMBER,
        "certificate_number":           GMPRecord.GMP_CERTIFICATE_NUMBER,
        "certificate_validity":         GMPRecord.GMP_CERTIFICATE_VALIDITY,
        "decision":                     GMPRecord.GMP_DECISION,
        "processed_time":               GMPRecord.GMP_PROCESSED_TIME,
        "timeline":                     GMPRecord.GMP_TIMELINE,
        "remarks":                      GMPRecord.GMP_REMARKS,
        "product_line":                 GMPRecord.GMP_PRODUCT_LINE,
    }
    for filter_key, column in TEXT_FIELD_COLUMNS.items():
        value = filters.get(filter_key)
        if value:
            query = query.filter(column.like(f"%{value}%"))

    # Extra per-column date-range filters — same "_from"/"_to" pattern as
    # upload_date / date_received above.
    DATE_RANGE_COLUMNS = {
        "released_date":                 GMPRecord.GMP_RELEASED_DATE,
        "end_date":                      GMPRecord.GMP_END_DATE,
        "date_printed":                  GMPRecord.GMP_DATE_PRINTED,
        "compliance_docs_date_received": GMPRecord.GMP_COMPLIANCE_DOCS_DATE_RECEIVED,
    }
    for filter_key, column in DATE_RANGE_COLUMNS.items():
        from_value = filters.get(f"{filter_key}_from")
        to_value   = filters.get(f"{filter_key}_to")
        if from_value:
            query = query.filter(column >= from_value)
        if to_value:
            query = query.filter(column <= to_value)

    if tab == "decked":
        decked_ids = _decked_subquery(db)
        query = query.filter(
            or_(GMPRecord.GMP_ID.in_(decked_ids), GMPRecord.GMP_APP_STATUS == "COMPLETED")
        )
    elif tab == "not_yet_decked":
        decked_ids = _decked_subquery(db)
        query = query.filter(
            GMPRecord.GMP_ID.notin_(decked_ids),
            or_(GMPRecord.GMP_APP_STATUS != "COMPLETED", GMPRecord.GMP_APP_STATUS.is_(None)),
        )

    if app_status:
        if app_status == "__EMPTY__":
            query = query.filter(
                or_(GMPRecord.GMP_APP_STATUS.is_(None), GMPRecord.GMP_APP_STATUS == "")
            )
        elif app_status == "IN PROGRESS":
            # Mirrors _effective_status_col(): a non-terminal (or blank)
            # status with an open current_step. NULL/"" must be OR'd in
            # explicitly — SQL's `NOT IN` evaluates to NULL, not TRUE, when
            # compared against a NULL column.
            not_terminal = or_(
                GMPRecord.GMP_APP_STATUS.is_(None),
                GMPRecord.GMP_APP_STATUS == "",
                func.upper(GMPRecord.GMP_APP_STATUS).notin_(GMP_TERMINAL_STATUSES),
            )
            query = query.filter(
                not_terminal,
                GMPRecord.GMP_CURRENT_STEP.isnot(None), GMPRecord.GMP_CURRENT_STEP != "",
            )
        else:
            query = query.filter(GMPRecord.GMP_APP_STATUS == app_status)

    if est_category:
        query = query.filter(GMPRecord.GMP_EST_CATEGORY == est_category)
    if pics_nonpics:
        query = query.filter(GMPRecord.GMP_PICS_NONPICS == pics_nonpics)
    if transaction_type:
        query = query.filter(GMPRecord.GMP_TRANSACTION_TYPE == transaction_type)
    if type_of_issuance:
        query = query.filter(GMPRecord.GMP_TYPE_OF_ISSUANCE == type_of_issuance)
    if current_step:
        query = query.filter(GMPRecord.GMP_CURRENT_STEP == current_step)
    if evaluator:
        query = query.filter(GMPRecord.GMP_EVALUATOR.like(f"%{evaluator}%"))

    if dtns and len(dtns) > 0:
        query = query.filter(GMPRecord.GMP_DTN.in_(dtns))
    elif dtn:
        query = query.filter(GMPRecord.GMP_DTN == dtn)

    if related_dtn:
        query = query.filter(GMPRecord.GMP_RELATED_DTN.like(f"%{related_dtn}%"))

    if lto_company:
        query = query.filter(GMPRecord.GMP_LTO_COMPANY.like(f"%{lto_company}%"))

    if uploaded_by:
        query = query.filter(GMPRecord.GMP_USER_UPLOADER.like(f"%{uploaded_by}%"))

    if upload_date_from:
        query = query.filter(GMPRecord.GMP_DATE_EXCEL_UPLOAD >= f"{upload_date_from} 00:00:00")
    if upload_date_to:
        query = query.filter(GMPRecord.GMP_DATE_EXCEL_UPLOAD <= f"{upload_date_to} 23:59:59")

    if date_received_from:
        query = query.filter(GMPRecord.GMP_DATE_RECEIVED >= date_received_from)
    if date_received_to:
        query = query.filter(GMPRecord.GMP_DATE_RECEIVED <= date_received_to)

    # "Duplicates" filter — meant for the Per-DTN (Main) view: surfaces DTNs
    # that have a genuine data-entry duplicate, i.e. TWO OR MORE of their own
    # reference records (primary + Add-Issuance siblings) share the same
    # Type of Issuance. This is distinct from legitimate siblings (same DTN,
    # DIFFERENT Type of Issuance), which are intentional and stay hidden.
    # Grouped/scoped by DTN rather than joined onto raw rows so it composes
    # cleanly with _primary_only() above — the primary row is kept, but only
    # for DTNs whose sibling family actually has a duplicate inside it.
    if filters.get("duplicates_only"):
        dupe_dtns_subq = (
            db.query(GMPRecord.GMP_DTN)
            .filter(
                GMPRecord.GMP_DTN.isnot(None),
                or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"),
            )
            .group_by(GMPRecord.GMP_DTN, GMPRecord.GMP_TYPE_OF_ISSUANCE)
            .having(func.count(GMPRecord.GMP_ID) > 1)
            .subquery()
        )
        query = query.filter(GMPRecord.GMP_DTN.in_(db.query(dupe_dtns_subq.c.GMP_DTN)))

    if search and not (dtns and len(dtns) > 0):
        p = f"%{search}%"
        conds = [
            GMPRecord.GMP_LTO_COMPANY.like(p),
            GMPRecord.GMP_LTO_NUMBER.like(p),
            GMPRecord.GMP_CERTIFICATE_NUMBER.like(p),
            GMPRecord.GMP_SECPA_NUMBER.like(p),
            GMPRecord.GMP_EST_CATEGORY.like(p),
        ]
        if search.isdigit():
            conds.append(GMPRecord.GMP_DTN == int(search))
        else:
            conds.append(cast(GMPRecord.GMP_DTN, String).like(p))
        query = query.filter(or_(*conds))

    total = query.count()

    delegation_sort_fields = [
        "GMP_DATE_DECKER_1_END", "GMP_DATE_EVALUATOR_END",
        "GMP_DATE_CHECKER_END", "GMP_DATE_QA_ADMIN_END",
        "GMP_DATE_LRD_CHIEF_END",
        "GMP_DATE_OD_RECEIVING_END", "GMP_DATE_OD_RELEASING_END",
    ]
    # A secondary sort key on the primary key is required — without it, rows
    # that tie on the primary sort column come back in a non-deterministic
    # order on every request (see same fix in crud/workflow_tasks.py).
    if sort_by in delegation_sort_fields:
        query = query.outerjoin(GMPDelegation, GMPRecord.GMP_ID == GMPDelegation.GMP_MAIN_ID)
        col = getattr(GMPDelegation, sort_by)
        query = query.order_by(
            nullslast(desc(col)) if sort_order.lower() == "desc" else nullslast(col),
            GMPRecord.GMP_ID,
        )
    elif hasattr(GMPRecord, sort_by):
        col = getattr(GMPRecord, sort_by)
        query = query.order_by(
            desc(col) if sort_order.lower() == "desc" else col, GMPRecord.GMP_ID
        )
    else:
        query = query.order_by(desc(GMPRecord.GMP_DATE_EXCEL_UPLOAD), GMPRecord.GMP_ID)

    query = query.options(joinedload(GMPRecord.gmp_delegation))
    records = query.offset(skip).limit(limit).all()

    # Main view: attach every sibling reference number's own issuance details
    # under the same DTN (added via Add Issuance) — one bulk query (indexed
    # GMP_DTN, single IN clause) rather than a per-row lookup, same pattern
    # as get_tasks_for_user's all_issuance_types in app/crud/gmp_logs.py.
    # GMPRecordResponse.all_issuances has no DB-mapped column, so every
    # record needs the attribute set to SOMETHING — Pydantic's
    # from_attributes reads it via getattr() and raises AttributeError on a
    # record that never got it set, which every non-"main" record would be.
    issuances_by_dtn: Dict[int, List[dict]] = {}
    related_dtn_by_dtn: Dict[int, str] = {}
    if view == "main":
        dtns_on_page = {r.GMP_DTN for r in records if r.GMP_DTN}
        if dtns_on_page:
            sibling_rows = (
                db.query(
                    GMPRecord.GMP_DTN, GMPRecord.GMP_REFERENCE_NO, GMPRecord.GMP_TYPE_OF_ISSUANCE,
                    GMPRecord.GMP_CERTIFICATE_NUMBER, GMPRecord.GMP_CERTIFICATE_VALIDITY, GMPRecord.GMP_SECPA_NUMBER,
                    GMPRecord.GMP_RELATED_DTN,
                )
                .filter(
                    GMPRecord.GMP_DTN.in_(dtns_on_page),
                    or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"),
                )
                .order_by(GMPRecord.GMP_REFERENCE_NO.asc())
                .all()
            )
            for dtn, ref_no, issuance, cert_no, cert_val, secpa, related_dtn in sibling_rows:
                issuances_by_dtn.setdefault(dtn, []).append({
                    "reference_no": ref_no, "type_of_issuance": issuance,
                    "certificate_number": cert_no, "certificate_validity": cert_val,
                    "secpa_number": secpa,
                })
                # The primary ('-01') reference is what "Per DTN" displays, but
                # Related DTN is sometimes only entered on a sibling reference
                # (e.g. via Add Issuance or a follow-up NFI/FROO branch) — fall
                # back to the first sibling that actually has one set, so the
                # rolled-up row doesn't show "—" when the data exists elsewhere
                # in the same DTN family.
                if related_dtn and dtn not in related_dtn_by_dtn:
                    related_dtn_by_dtn[dtn] = related_dtn
    for r in records:
        r.all_issuances = issuances_by_dtn.get(r.GMP_DTN, [])
        if not r.GMP_RELATED_DTN and r.GMP_DTN in related_dtn_by_dtn:
            r.GMP_RELATED_DTN = related_dtn_by_dtn[r.GMP_DTN]

    return records, total


# ── Logs ──────────────────────────────────────────────────────────────────────
def get_gmp_logs(
    db: Session, gmp_id: int, skip: int = 0, limit: int = 50
) -> Tuple[List[GMPApplicationLogs], int]:
    query = db.query(GMPApplicationLogs).filter(
        GMPApplicationLogs.gmp_record_id == gmp_id
    )
    total = query.count()
    logs = (
        query.order_by(GMPApplicationLogs.del_index.asc())
        .offset(skip).limit(limit).all()
    )
    return logs, total


# ── Create / Update ───────────────────────────────────────────────────────────
def create_gmp_record(
    db: Session,
    record: GMPRecordCreate,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> GMPRecord:
    data = record.model_dump(exclude_unset=True)
    if "GMP_DATE_EXCEL_UPLOAD" not in data or data["GMP_DATE_EXCEL_UPLOAD"] is None:
        data["GMP_DATE_EXCEL_UPLOAD"] = _now()
    if data.get("GMP_DTN") and not data.get("GMP_REFERENCE_NO"):
        data["GMP_REFERENCE_NO"] = _next_reference_no(db, data["GMP_DTN"])
    db_record = GMPRecord(**data)
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    after = {f: getattr(db_record, f) for f in data.keys()}
    log_field_changes(db, db_record.GMP_ID, {f: None for f in data.keys()}, after,
                      action_type="CREATE", user_name=user_name, user_id=user_id)
    return db_record


def update_gmp_record(
    db: Session,
    record_id: int,
    record_update: GMPRecordUpdate,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[GMPRecord]:
    db_record = get_gmp_record(db, record_id)
    if not db_record:
        return None
    update_data = record_update.model_dump(exclude_unset=True)
    before = {f: getattr(db_record, f) for f in update_data.keys()}
    for f, v in update_data.items():
        setattr(db_record, f, v)
    db.commit()
    db.refresh(db_record)
    after = {f: getattr(db_record, f) for f in update_data.keys()}
    log_field_changes(db, record_id, before, after,
                      action_type="UPDATE", user_name=user_name, user_id=user_id)
    # Propagate shared (non-issuance-specific) field changes to every other
    # reference number under the same DTN.
    _sync_to_siblings(db, db_record, after)
    return db_record


# ── Delete ────────────────────────────────────────────────────────────────────
def delete_gmp_record(
    db: Session, record_id: int,
    user_name: Optional[str] = None, user_id: Optional[int] = None,
) -> bool:
    db_record = get_gmp_record(db, record_id)
    if not db_record:
        return False
    before = {"GMP_TRASH": db_record.GMP_TRASH}
    db_record.GMP_TRASH = "deleted"
    db_record.GMP_TRASH_DATE_ENCODED = _now()
    db.commit()
    log_field_changes(db, record_id, before, {"GMP_TRASH": "deleted"},
                      action_type="DELETE", user_name=user_name, user_id=user_id)
    return True


def hard_delete_gmp_record(db: Session, record_id: int) -> bool:
    db_record = get_gmp_record(db, record_id)
    if not db_record:
        return False
    db.delete(db_record)
    db.commit()
    return True

# ── Reference number generation ───────────────────────────────────────────────
def _next_reference_no(db: Session, dtn: int) -> str:
    """Next sequential {DTN}-{NN} reference number for a given DTN group."""
    existing = (
        db.query(GMPRecord.GMP_REFERENCE_NO)
        .filter(GMPRecord.GMP_DTN == dtn, GMPRecord.GMP_REFERENCE_NO.isnot(None))
        .all()
    )
    max_seq = 0
    for (ref,) in existing:
        try:
            seq = int(str(ref).rsplit("-", 1)[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    return f"{dtn}-{max_seq + 1:02d}"


# Issuance types that carry NO certificate at all — Certificate Number,
# Certificate Validity, and SECPA Number are all blanked.
GMP_NO_CERT_ISSUANCE_TYPES = {
    "Notice for Inspection - Fresh Application",
    "Notice for Inspection - Renewal Application",
    "NFI due to Non-compliance",
    "Permit to Register",
    "Letter of Disapproval",
}
# Issuance types that carry a Certificate Number + Certificate Validity but
# NO SECPA Number.
GMP_NO_SECPA_ONLY_TYPES = {
    "Extension of Validity",
}
# Everything else (CGMP Clearance, CGMP Clearance - COC) carries all three.


def _apply_issuance_cert_rules(data: dict, type_of_issuance: str) -> dict:
    """Blanks Certificate Number / Certificate Validity / SECPA Number on
    `data` according to which tier `type_of_issuance` falls into."""
    if type_of_issuance in GMP_NO_CERT_ISSUANCE_TYPES:
        data["GMP_CERTIFICATE_NUMBER"] = None
        data["GMP_CERTIFICATE_VALIDITY"] = None
        data["GMP_SECPA_NUMBER"] = None
    elif type_of_issuance in GMP_NO_SECPA_ONLY_TYPES:
        data["GMP_SECPA_NUMBER"] = None
    return data


# Fields that auto-sync across every reference number sharing a DTN whenever
# any one of them is updated — everything EXCEPT identity fields, metadata,
# and the issuance-specific certificate fields (Type of Issuance, Certificate
# Number, Certificate Validity, SECPA Number). Certificate Number and
# Certificate Validity ARE additionally synced when the sibling being synced
# TO has Type of Issuance == "Extension of Validity" (its own cert follows
# the same numbers as the rest of the application) — see _sync_to_siblings.
GMP_NON_SYNC_FIELDS = {
    "GMP_ID", "GMP_REFERENCE_NO", "GMP_DTN",
    "GMP_TYPE_OF_ISSUANCE", "GMP_CERTIFICATE_NUMBER",
    "GMP_CERTIFICATE_VALIDITY", "GMP_SECPA_NUMBER",
    "GMP_TRASH", "GMP_TRASH_DATE_ENCODED",
    "GMP_DATE_EXCEL_UPLOAD", "GMP_USER_UPLOADER",
}


def _sync_to_siblings(db: Session, record: GMPRecord, changed_fields: dict) -> None:
    """
    Propagates shared-field changes from `record` to every other GMPRecord
    sharing its DTN. Only fields in `changed_fields` that aren't in
    GMP_NON_SYNC_FIELDS are synced — except Certificate Number / Certificate
    Validity, which ARE synced onto a sibling if that sibling's own Type of
    Issuance is "Extension of Validity" (per the "same DTN, same underlying
    numbers" rule for that issuance type specifically).
    """
    if not record.GMP_DTN:
        return
    siblings = (
        db.query(GMPRecord)
        .filter(GMPRecord.GMP_DTN == record.GMP_DTN, GMPRecord.GMP_ID != record.GMP_ID)
        .all()
    )
    if not siblings:
        return

    base_sync = {k: v for k, v in changed_fields.items() if k not in GMP_NON_SYNC_FIELDS}
    cert_sync = {k: v for k, v in changed_fields.items()
                 if k in ("GMP_CERTIFICATE_NUMBER", "GMP_CERTIFICATE_VALIDITY")}

    for sib in siblings:
        for f, v in base_sync.items():
            setattr(sib, f, v)
        if sib.GMP_TYPE_OF_ISSUANCE == "Extension of Validity":
            for f, v in cert_sync.items():
                setattr(sib, f, v)
    db.commit()


# ── Sibling reference numbers ─────────────────────────────────────────────────
def get_gmp_siblings(db: Session, record_id: int) -> List[GMPRecord]:
    """All GMPRecord rows sharing the same DTN as `record_id`, including
    itself, ordered by GMP_REFERENCE_NO (so -01 sorts first)."""
    record = get_gmp_record(db, record_id)
    if not record or not record.GMP_DTN:
        return [record] if record else []
    return (
        db.query(GMPRecord)
        .filter(GMPRecord.GMP_DTN == record.GMP_DTN)
        .order_by(GMPRecord.GMP_REFERENCE_NO.asc())
        .all()
    )


def is_primary_reference(record: GMPRecord) -> bool:
    """The '-01' reference number is the only one with an active workflow —
    every other reference number under the same DTN is an attached issuance
    variant that mirrors the primary's shared fields and current step but
    never gets its own application logs / task assignment."""
    ref = record.GMP_REFERENCE_NO or ""
    return ref.endswith("-01")


def update_gmp_issuance_fields(
    db: Session,
    record_id: int,
    type_of_issuance: Optional[str] = None,
    certificate_number: Optional[str] = None,
    certificate_validity: Optional[str] = None,
    secpa_number: Optional[str] = None,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[GMPRecord]:
    """
    Updates only the issuance-specific fields on a single reference number
    (primary or sibling) — does NOT touch workflow state and does NOT sync
    to siblings, since these fields are intentionally per-issuance.
    Re-applies the certificate-tier blanking rules whenever type_of_issuance
    changes, so switching e.g. CGMP Clearance -> Letter of Disapproval
    correctly clears the now-inapplicable cert fields.
    """
    record = get_gmp_record(db, record_id)
    if not record:
        return None
    before = {
        "GMP_TYPE_OF_ISSUANCE": record.GMP_TYPE_OF_ISSUANCE,
        "GMP_CERTIFICATE_NUMBER": record.GMP_CERTIFICATE_NUMBER,
        "GMP_CERTIFICATE_VALIDITY": record.GMP_CERTIFICATE_VALIDITY,
        "GMP_SECPA_NUMBER": record.GMP_SECPA_NUMBER,
    }
    data = dict(before)
    if type_of_issuance is not None:
        data["GMP_TYPE_OF_ISSUANCE"] = type_of_issuance
    if certificate_number is not None:
        data["GMP_CERTIFICATE_NUMBER"] = certificate_number
    if certificate_validity is not None:
        data["GMP_CERTIFICATE_VALIDITY"] = certificate_validity
    if secpa_number is not None:
        data["GMP_SECPA_NUMBER"] = secpa_number

    effective_type = data["GMP_TYPE_OF_ISSUANCE"]
    data = _apply_issuance_cert_rules(data, effective_type)

    for f, v in data.items():
        setattr(record, f, v)
    db.commit()
    db.refresh(record)
    log_field_changes(db, record_id, before, data, action_type="UPDATE",
                      user_name=user_name, user_id=user_id)
    return record


# ── Assign evaluator ──────────────────────────────────────────────────────────


def add_gmp_issuance(
    db: Session,
    record_id: int,
    type_of_issuance: str,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[GMPRecord]:
    """
    Duplicate an existing GMPRecord under the same DTN with a different
    GMP_TYPE_OF_ISSUANCE. Only the '-01' (primary) reference number ever
    carries an actual workflow — the new reference number gets NO
    application logs and NO delegation row of its own, so it never appears
    as a separate task. Its GMP_CURRENT_STEP is a display-only snapshot of
    the original's, kept in sync going forward whenever the primary advances
    (see advance_step in app/crud/gmp_logs.py) or any shared field changes
    (see _sync_to_siblings above).

    Also drops a system entry (action_type="ISSUANCE_ADDED") onto the
    PRIMARY record's own Application Logs timeline recording when this
    happened and what was added — the new sibling has no logs of its own to
    carry that date/time, so without this the addition would be invisible in
    the Application Logs modal / WorkflowModal Step 3 (see log_field_changes
    below for the separate, lower-level field-audit-trail entry).
    """
    original = get_gmp_record(db, record_id)
    if not original or not original.GMP_DTN:
        return None

    skip_cols = {"GMP_ID", "GMP_REFERENCE_NO", "GMP_TYPE_OF_ISSUANCE",
                 "GMP_CERTIFICATE_NUMBER", "GMP_CERTIFICATE_VALIDITY", "GMP_SECPA_NUMBER",
                 "GMP_DATE_EXCEL_UPLOAD", "GMP_USER_UPLOADER"}
    data = {}
    for col in GMPRecord.__table__.columns.keys():
        if col in skip_cols:
            continue
        data[col] = getattr(original, col)

    cert_data = _apply_issuance_cert_rules({
        "GMP_CERTIFICATE_NUMBER": original.GMP_CERTIFICATE_NUMBER,
        "GMP_CERTIFICATE_VALIDITY": original.GMP_CERTIFICATE_VALIDITY,
        "GMP_SECPA_NUMBER": original.GMP_SECPA_NUMBER,
    }, type_of_issuance)

    new_record = GMPRecord(
        **data,
        **cert_data,
        GMP_TYPE_OF_ISSUANCE=type_of_issuance,
        GMP_REFERENCE_NO=_next_reference_no(db, original.GMP_DTN),
        GMP_DATE_EXCEL_UPLOAD=_now(),
        GMP_USER_UPLOADER=user_name,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    # ── System log entry on the PRIMARY record — this is what actually
    # surfaces the "date/time added" in the Application Logs timeline. Closed
    # immediately (del_thread="Close") so it's purely informational and never
    # competes with the record's real single "Open" thread.
    last_index = (
        db.query(func.max(GMPApplicationLogs.del_index))
        .filter(GMPApplicationLogs.gmp_record_id == record_id)
        .scalar()
    ) or 0
    now = _now()
    db.add(GMPApplicationLogs(
        gmp_record_id=record_id,
        application_step=original.GMP_CURRENT_STEP,
        application_status="COMPLETED",
        application_decision="",
        application_remarks=f"Type of Issuance Added: {type_of_issuance} (Ref {new_record.GMP_REFERENCE_NO})",
        action_type="ISSUANCE_ADDED",
        start_date=now,
        accomplished_date=now,
        del_index=last_index + 1,
        del_previous=last_index if last_index > 0 else None,
        del_last_index=0,
        del_thread="Close",
        user_name=user_name,
        user_id=user_id,
        is_received=0,
        is_starred=0,
        sent_by_user_id=user_id,
        sent_by_user_name=user_name,
    ))
    db.commit()

    after = {f: getattr(new_record, f) for f in data.keys()}
    after.update(cert_data)
    after["GMP_TYPE_OF_ISSUANCE"] = type_of_issuance
    after["GMP_REFERENCE_NO"] = new_record.GMP_REFERENCE_NO
    log_field_changes(db, new_record.GMP_ID, {f: None for f in after.keys()}, after,
                      action_type="CREATE", user_name=user_name, user_id=user_id)
    return new_record


# ── Reopen a finished application back to Decking ──────────────────────────
def reopen_gmp_to_decking(
    db: Session,
    record_id: int,
    related_dtn: str,
    user_name: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Optional[GMPRecord]:
    """
    Reopen a finished application back to Decking — used when a follow-up DTN
    (e.g. the physical inspection that results from an NFI) comes back in and
    THIS SAME application needs to continue, rather than spawning a new
    record under a new reference number (that duplicated the record instead
    of reopening it — see the previous version of this function).

    Nothing is copied and no new GMPRecord/reference number is created: it's
    the same GMP_ID, so its field and log history is already exactly where
    it should be. This just:
      1. Records the Related DTN on the record itself.
      2. Clears GMP_APP_STATUS (was a terminal value like "RELEASED") and
         Type of Issuance / certificate fields (the follow-up may resolve to
         a different issuance type — picked fresh at Decking, same as
         add_gmp_issuance leaves them for a new sibling reference number).
      3. Opens a new "Decking" / IN PROGRESS log (like the Evaluator "For
         Compliance" self-loop does — closed history stays, a fresh entry is
         appended), which is what makes the record read as back in progress
         and puts it in front of whoever decks it next via the normal Deck
         Application action.
    """
    record = get_gmp_record(db, record_id)
    if not record or not record.GMP_DTN:
        return None

    before = {
        "GMP_RELATED_DTN": record.GMP_RELATED_DTN,
        "GMP_APP_STATUS": record.GMP_APP_STATUS,
        "GMP_CURRENT_STEP": record.GMP_CURRENT_STEP,
        "GMP_TYPE_OF_ISSUANCE": record.GMP_TYPE_OF_ISSUANCE,
        "GMP_CERTIFICATE_NUMBER": record.GMP_CERTIFICATE_NUMBER,
        "GMP_CERTIFICATE_VALIDITY": record.GMP_CERTIFICATE_VALIDITY,
        "GMP_SECPA_NUMBER": record.GMP_SECPA_NUMBER,
    }
    record.GMP_RELATED_DTN = related_dtn
    record.GMP_APP_STATUS = None
    record.GMP_CURRENT_STEP = "Decking"
    record.GMP_TYPE_OF_ISSUANCE = None
    record.GMP_CERTIFICATE_NUMBER = None
    record.GMP_CERTIFICATE_VALIDITY = None
    record.GMP_SECPA_NUMBER = None
    db.commit()
    db.refresh(record)

    last_index = (
        db.query(func.max(GMPApplicationLogs.del_index))
        .filter(GMPApplicationLogs.gmp_record_id == record_id)
        .scalar()
    ) or 0
    now = _now()
    db.add(GMPApplicationLogs(
        gmp_record_id=record_id,
        application_step="Decking",
        application_status="IN PROGRESS",
        application_decision="",
        application_remarks=f"Application reopened — Related DTN {related_dtn}.",
        start_date=now,
        del_index=last_index + 1,
        del_previous=last_index if last_index > 0 else None,
        del_last_index=1,
        del_thread="Open",
        user_name=user_name,
        user_id=user_id,
        is_received=0,
        is_starred=0,
        sent_by_user_id=user_id,
        sent_by_user_name=user_name,
    ))
    db.commit()
    db.refresh(record)

    after = {
        "GMP_RELATED_DTN": related_dtn,
        "GMP_APP_STATUS": None,
        "GMP_CURRENT_STEP": "Decking",
        "GMP_TYPE_OF_ISSUANCE": None,
        "GMP_CERTIFICATE_NUMBER": None,
        "GMP_CERTIFICATE_VALIDITY": None,
        "GMP_SECPA_NUMBER": None,
    }
    log_field_changes(db, record_id, before, after, action_type="UPDATE",
                      user_name=user_name, user_id=user_id)
    return record


# ── Assign evaluator ──────────────────────────────────────────────────────────
def assign_evaluator(
    db: Session, record_id: int, evaluator_name: str,
    user_name: Optional[str] = None, user_id: Optional[int] = None,
) -> Optional[GMPRecord]:
    db_record = get_gmp_record(db, record_id)
    if not db_record:
        return None
    before = {"GMP_EVALUATOR": db_record.GMP_EVALUATOR}
    db_record.GMP_EVALUATOR = evaluator_name
    db.commit()
    db.refresh(db_record)
    log_field_changes(db, record_id, before, {"GMP_EVALUATOR": evaluator_name},
                      action_type="UPDATE", user_name=user_name, user_id=user_id)

    if evaluator_name and db_record.GMP_DTN is not None:
        try:
            dtn = str(db_record.GMP_DTN)
            if not already_notified_today(db, evaluator_name, dtn, title_like="Evaluator Assignment"):
                create_notification(
                    db,
                    NotificationCreate(
                        user_name=evaluator_name,
                        title="🔬 New GMP Evaluator Assignment",
                        message=f"You have been assigned as evaluator for DTN: {dtn}.",
                        link_dtn=dtn,
                    ),
                )
        except Exception:
            pass  # notification failure must never crash the main operation

    return db_record


# ── Bulk ──────────────────────────────────────────────────────────────────────
def bulk_create_gmp_records(
    db: Session, records: List[GMPRecordCreate]
) -> List[GMPRecord]:
    db_records = []
    for record in records:
        data = record.model_dump(exclude_unset=True)
        if "GMP_DATE_EXCEL_UPLOAD" not in data:
            data["GMP_DATE_EXCEL_UPLOAD"] = _now()
        db_records.append(GMPRecord(**data))
    db.add_all(db_records)
    db.commit()
    for r in db_records:
        db.refresh(r)
    return db_records


def bulk_delete_gmp_records(db: Session, record_ids: List[int]) -> int:
    if not record_ids:
        return 0
    try:
        count = (
            db.query(GMPRecord)
            .filter(GMPRecord.GMP_ID.in_(record_ids))
            .update(
                {"GMP_TRASH": "deleted", "GMP_TRASH_DATE_ENCODED": _now()},
                synchronize_session=False,
            )
        )
        db.commit()
        return count
    except Exception as e:
        db.rollback()
        print(f"Error bulk deleting GMP records: {e}")
        return 0


# ── Summary ───────────────────────────────────────────────────────────────────
def get_gmp_summary(db: Session) -> dict:
    not_trashed = or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted")
    # "total" mirrors the "All Reports" tab, which lists every reference
    # number as its own row — so it's counted without the primary-only
    # filter. Decked/not-decked/status/category counts stay primary-only
    # since workflow state only ever lives on the primary ('-01') record.
    total = db.query(GMPRecord).filter(not_trashed).count()
    base = _primary_only(db.query(GMPRecord).filter(not_trashed))
    decked_ids = _decked_subquery(db)
    decked = base.filter(
        or_(GMPRecord.GMP_ID.in_(decked_ids), GMPRecord.GMP_APP_STATUS == "COMPLETED")
    ).count()
    not_decked = base.filter(
        GMPRecord.GMP_ID.notin_(decked_ids),
        or_(GMPRecord.GMP_APP_STATUS != "COMPLETED", GMPRecord.GMP_APP_STATUS.is_(None)),
    ).count()
    status_counts = (
        _primary_only(
            db.query(GMPRecord.GMP_APP_STATUS, func.count(GMPRecord.GMP_ID))
            .filter(or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"))
        )
        .group_by(GMPRecord.GMP_APP_STATUS).all()
    )
    category_counts = (
        _primary_only(
            db.query(GMPRecord.GMP_EST_CATEGORY, func.count(GMPRecord.GMP_ID))
            .filter(or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"))
        )
        .group_by(GMPRecord.GMP_EST_CATEGORY).all()
    )
    seven_days_ago = _now() - timedelta(days=7)
    recent = base.filter(GMPRecord.GMP_DATE_EXCEL_UPLOAD >= seven_days_ago).count()
    return {
        "total_records": total,
        "decked_count": decked,
        "not_decked_count": not_decked,
        "by_status": {s or "Unknown": c for s, c in status_counts},
        "by_category": {cat or "Unknown": c for cat, c in category_counts},
        "recent_uploads": recent,
    }


# ── Facet helpers ─────────────────────────────────────────────────────────────
def get_unique_values(db: Session, field: str) -> List[str]:
    if not hasattr(GMPRecord, field):
        return []
    col = getattr(GMPRecord, field)
    results = (
        db.query(col)
        .filter(or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"))
        .distinct().filter(col.isnot(None)).all()
    )
    return [r[0] for r in results if r[0]]


def get_field_counts(
    db: Session, field: str, tab: Optional[str] = None, view: Optional[str] = None,
    empty_value: Optional[str] = None, empty_label: str = "(Empty)",
) -> List[dict]:
    if field == "GMP_APP_STATUS":
        col = _effective_status_col()
    elif not hasattr(GMPRecord, field):
        return []
    else:
        col = getattr(GMPRecord, field)

    def _base():
        q = db.query(GMPRecord).filter(
            or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted")
        )
        # Mirrors get_gmp_records: view="main" always counts one row per DTN
        # regardless of tab; "Decked"/"Not Yet Decked" only ever count the
        # primary ('-01') reference too, since that's the only one workflow
        # state (decking status) lives on. Otherwise ("all" + no tab) counts
        # every reference number as its own row.
        if view == "main" or tab in ("decked", "not_yet_decked"):
            q = _primary_only(q)
        if tab == "decked":
            decked_ids = _decked_subquery(db)
            q = q.filter(
                or_(GMPRecord.GMP_ID.in_(decked_ids), GMPRecord.GMP_APP_STATUS == "COMPLETED")
            )
        elif tab == "not_yet_decked":
            decked_ids = _decked_subquery(db)
            q = q.filter(
                GMPRecord.GMP_ID.notin_(decked_ids),
                or_(GMPRecord.GMP_APP_STATUS != "COMPLETED", GMPRecord.GMP_APP_STATUS.is_(None)),
            )
        return q

    results = (
        _base().with_entities(col, func.count(GMPRecord.GMP_ID))
        .filter(col.isnot(None), col != "")
        .group_by(col).order_by(col).all()
    )
    items = [{"value": v, "label": v, "count": c} for v, c in results]

    # Records with a blank/null value for this field are otherwise dropped
    # from the sidebar entirely (isnot(None) above) — invisible even though
    # they're real rows counted in "All". get_gmp_records already supports
    # filtering app_status by the "__EMPTY__" sentinel; surface it here too
    # so those rows are actually reachable from the sidebar, not just implied
    # by "All" minus the sum of the listed values.
    if empty_value is not None:
        empty_count = _base().filter(or_(col.is_(None), col == "")).count()
        if empty_count > 0:
            items.append({"value": empty_value, "label": empty_label, "count": empty_count})

    return items
