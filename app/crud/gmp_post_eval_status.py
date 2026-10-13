# app/crud/gmp_post_eval_status.py
# "Post-Evaluation Status" — FGMP Dashboard-only card. Answers "what have I
# finished my part on that isn't released yet, and where is it now?" for the
# logged-in Evaluator / Checker / any other FGMP step owner. No CPR
# counterpart — this is scoped to GMPRecord / GMPApplicationLogs only.
#
# Every application lands in one of two groups:
#   "returned" — it is sitting back on the step YOU last completed, either
#                because someone downstream sent it back or because it never
#                left (the Evaluator's "For Compliance" self-loop). Yours to
#                act on, and labelled with WHO sent it back.
#   "forward"  — it moved on and is with someone else. Labelled with the step
#                it is sitting at, one step per label, never lumped together.

from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List, Dict, Tuple
import math

from app.models.gmp_record import GMPApplicationLogs, GMPRecord
from app.crud.gmp_logs import _assignee_match
from app.crud.gmp_record import GMP_LOG_STEPS

GROUP_RETURNED = "returned"
GROUP_FORWARD = "forward"

# `bucket` values get_rows accepts beyond an exact label match.
BUCKET_ALL = "all"
BUCKET_RETURNED = "returned"

# Workflow order, so the "Moved forward" chips read the way an application
# actually travels (Checker → QA Admin → …) instead of alphabetically.
_STEP_ORDER: Dict[str, int] = {
    label: idx for idx, (label, _) in enumerate(GMP_LOG_STEPS)
}

RETURNED_BY_PREFIX = "Returned by "

# Wording for return actions that need more than the generic
# "Returned by <step>". Keys are (step, decision) pairs straight out of
# GMP_ACTION_ROUTES (app/crud/gmp_record.py) — keep them in sync with it.
#
# The two Checker returns are deliberately NOT given the same label: "Checked
# and returned to evaluator" means the check is done and the application can
# move on, while the "Not Checked" one means the Checker never checked it and
# the evaluator has to fix something first. Same destination, opposite work,
# so they must not read alike on the card.
RETURN_LABEL_OVERRIDES: Dict[Tuple[str, str], str] = {
    ("Evaluator", "For Compliance"): "For Compliance",
    (
        "Checker",
        "Return to evaluator for review (Not Checked, Doctrack Remarks Off)",
    ): "Sent back — not checked",
}


def _my_active_record_ids(db: Session, username: Optional[str], user_id: Optional[int]):
    """
    Every GMPRecord where the current user COMPLETED at least one step, and
    the application is still actively moving — GMP_CURRENT_STEP is only
    cleared to NULL once the workflow truly ends (Released, or Disapproved;
    see the "final step" branch of advance_step in app/crud/gmp_logs.py), so
    a non-null value here means it is still somewhere in the workflow.

    Restricted to PRIMARY ('-01') reference numbers only, same guard
    get_tasks_for_user uses (app/crud/gmp_logs.py) — a DTN can have sibling
    GMPRecord rows (added via Add Issuance), and only the primary one should
    ever carry logs going forward, but legacy data sometimes has logs on a
    sibling too. Without this, a DTN with that legacy pattern shows up twice.
    """
    return (
        db.query(GMPApplicationLogs.gmp_record_id)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .filter(
            _assignee_match(username, user_id),
            GMPApplicationLogs.application_status == "COMPLETED",
            GMPRecord.GMP_CURRENT_STEP.isnot(None),
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
        .distinct()
    )


def _latest_completed_meta(db: Session, record_ids) -> Dict[int, Tuple[str, str]]:
    """{record_id: (step, decision)} — each record's most recent COMPLETED
    log, whoever completed it.

    This is the only thing that can tell a return apart from a fresh arrival.
    GMP_CURRENT_STEP says WHERE an application is, never how it got there:
    the Evaluator's "For Compliance" self-loop leaves it unchanged, and all
    three of the Checker/QA Admin returns set it to the same "Evaluator"
    value that Decking's forward hand-off does. The last decision taken on
    the record is what separates them.
    """
    if not record_ids:
        return {}
    latest = (
        db.query(
            GMPApplicationLogs.gmp_record_id,
            func.max(GMPApplicationLogs.del_index).label("max_idx"),
        )
        .filter(
            GMPApplicationLogs.gmp_record_id.in_(record_ids),
            GMPApplicationLogs.application_status == "COMPLETED",
        )
        .group_by(GMPApplicationLogs.gmp_record_id)
        .subquery()
    )
    rows = (
        db.query(
            GMPApplicationLogs.gmp_record_id,
            GMPApplicationLogs.application_step,
            GMPApplicationLogs.application_decision,
        )
        .join(
            latest,
            (GMPApplicationLogs.gmp_record_id == latest.c.gmp_record_id)
            & (GMPApplicationLogs.del_index == latest.c.max_idx),
        )
        .all()
    )
    return {rid: (step, decision) for rid, step, decision in rows}


def _return_label(
    step: Optional[str], decision: Optional[str], current_step: Optional[str]
) -> Optional[str]:
    """The label shown for an application that came back. Falls back to
    "Returned by <step>" for any route not spelled out in
    RETURN_LABEL_OVERRIDES, so a new return route added to GMP_ACTION_ROUTES
    still reads correctly without a change here."""
    override = RETURN_LABEL_OVERRIDES.get((step, decision))
    if override:
        return override
    if step:
        return f"{RETURNED_BY_PREFIX}{step}"
    return current_step


def _resolve(db: Session, username: Optional[str], user_id: Optional[int]) -> List[dict]:
    """Every qualifying record with the label the card shows for it, newest
    record first.

    One pass shared by get_step_breakdown and get_rows, so the header counts
    and the list they filter can never disagree. Only ids and log fields are
    read here; DTN / company are fetched by get_rows for the one page it
    actually returns.
    """
    ids_subq = _my_active_record_ids(db, username, user_id).subquery()
    records = (
        db.query(GMPRecord.GMP_ID, GMPRecord.GMP_CURRENT_STEP)
        .filter(GMPRecord.GMP_ID.in_(db.query(ids_subq.c.gmp_record_id)))
        .order_by(GMPRecord.GMP_ID.desc())
        .all()
    )
    record_ids = [rid for rid, _ in records]

    # "Your step" — this user's most recently completed log per record (they
    # can complete more than one step on the same record over its life).
    # Ordered so, within each record_id group, the highest del_index (most
    # recent) comes first; setdefault then keeps only that first hit.
    my_log_by_record: Dict[int, GMPApplicationLogs] = {}
    if record_ids:
        my_logs = (
            db.query(GMPApplicationLogs)
            .filter(
                GMPApplicationLogs.gmp_record_id.in_(record_ids),
                _assignee_match(username, user_id),
                GMPApplicationLogs.application_status == "COMPLETED",
            )
            .order_by(
                GMPApplicationLogs.gmp_record_id,
                GMPApplicationLogs.del_index.desc(),
            )
            .all()
        )
        for log in my_logs:
            my_log_by_record.setdefault(log.gmp_record_id, log)

    latest_meta = _latest_completed_meta(db, record_ids)

    resolved: List[dict] = []
    for rid, current_step in records:
        my_log = my_log_by_record.get(rid)
        your_step = my_log.application_step if my_log else None

        # Back with you when the application is sitting on the very step you
        # last completed. Deliberately compared against YOUR step rather than
        # hard-coded to "Evaluator": a QA Admin whose work came back from LRD
        # Chief Admin is in exactly the same position and reads the same way.
        is_return = bool(current_step) and current_step == your_step
        if is_return:
            step, decision = latest_meta.get(rid, (None, None))
            label = _return_label(step, decision, current_step)
        else:
            label = current_step

        resolved.append({
            "gmp_id": rid,
            "current_step": current_step,
            "your_step": your_step,
            "completed_date": my_log.accomplished_date if my_log else None,
            "label": label,
            "is_return": is_return,
        })
    return resolved


def _matches(row: dict, bucket: Optional[str]) -> bool:
    """Whether a resolved row belongs under `bucket` — "all"/None for
    everything, "returned" for every return at once, otherwise an exact match
    on the label get_step_breakdown handed out."""
    if not bucket or bucket == BUCKET_ALL:
        return True
    if bucket == BUCKET_RETURNED:
        return row["is_return"]
    return row["label"] == bucket


def get_step_breakdown(
    db: Session, username: Optional[str], user_id: Optional[int] = None
) -> List[dict]:
    """The card header's chips — one entry per label, each tagged with the
    group it renders under:

        [{"step": "Returned by Checker", "count": 1, "group": "returned"},
         {"step": "Sent back — not checked", "count": 1, "group": "returned"},
         {"step": "Checker", "count": 2, "group": "forward"},
         {"step": "QA Admin", "count": 1, "group": "forward"}]

    Returns come first, then the forward steps in workflow order. Each
    entry's "step" is what get_rows accepts as its `bucket`.
    """
    counts: Dict[str, int] = {}
    groups: Dict[str, str] = {}
    for row in _resolve(db, username, user_id):
        label = row["label"]
        if not label:
            continue
        counts[label] = counts.get(label, 0) + 1
        groups[label] = GROUP_RETURNED if row["is_return"] else GROUP_FORWARD

    def sort_key(label: str):
        if groups[label] == GROUP_RETURNED:
            return (0, 0, label)
        return (1, _STEP_ORDER.get(label, len(_STEP_ORDER)), label)

    return [
        {"step": label, "count": counts[label], "group": groups[label]}
        for label in sorted(counts, key=sort_key)
    ]


def _hydrate(db: Session, resolved: List[dict]) -> List[dict]:
    """Attach DTN / company to resolved rows. Kept separate from _resolve so
    the list endpoint pays for it on one page only, while the export pays for
    it on everything it is about to write out."""
    if not resolved:
        return []

    detail = {
        rec[0]: rec
        for rec in db.query(
            GMPRecord.GMP_ID, GMPRecord.GMP_DTN, GMPRecord.GMP_LTO_COMPANY
        )
        .filter(GMPRecord.GMP_ID.in_([r["gmp_id"] for r in resolved]))
        .all()
    }

    rows = []
    for r in resolved:
        rec = detail.get(r["gmp_id"])
        rows.append({
            "gmp_id": r["gmp_id"],
            "dtn": str(rec[1]) if rec is not None and rec[1] is not None else None,
            "lto_company": rec[2] if rec is not None else None,
            "your_step": r["your_step"],
            "completed_date": r["completed_date"],
            "current_step": r["current_step"],
            # None for anything that moved forward — the UI then falls back to
            # current_step and draws it as a pale "elsewhere" chip.
            "return_reason": r["label"] if r["is_return"] else None,
            "label": r["label"],
            "group": GROUP_RETURNED if r["is_return"] else GROUP_FORWARD,
        })
    return rows


def get_export_rows(
    db: Session,
    username: Optional[str],
    user_id: Optional[int] = None,
    buckets: Optional[List[str]] = None,
) -> List[dict]:
    """Every row under ANY of `buckets` — a union, de-duplicated by virtue of
    each record resolving to exactly one label — unpaginated, for the Excel
    export. Empty/None, or a list containing "all", means everything.

    Unknown bucket names are ignored rather than rejected: the caller builds
    them from a summary that may be a few seconds stale, and silently
    exporting a bucket that just emptied beats failing the download.
    """
    resolved = _resolve(db, username, user_id)
    wanted = {b for b in (buckets or []) if b}
    if wanted and BUCKET_ALL not in wanted:
        resolved = [r for r in resolved if any(_matches(r, b) for b in wanted)]
    return _hydrate(db, resolved)


def get_rows(
    db: Session,
    username: Optional[str],
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 10,
    bucket: Optional[str] = None,
) -> dict:
    """One row per application (never per log — a user can complete more than
    one step on the same record over its life; this collapses to their most
    recent completed step on it).

    Filtering and paging happen in Python rather than SQL because the labels
    are derived (see _resolve), and a count that disagreed with the rows under
    it would be worse than the extra ids in memory: the set is only "what I
    finished that is still moving", never the whole table.
    """
    page = max(1, page)
    page_size = max(1, min(50, page_size))

    resolved = [r for r in _resolve(db, username, user_id) if _matches(r, bucket)]
    total = len(resolved)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    window = resolved[start : start + page_size]

    # DTN / company are only needed for the rows actually going out.
    rows = _hydrate(db, window)

    return {"rows": rows, "total": total, "total_pages": total_pages, "page": page}
