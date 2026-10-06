# app/crud/checklist.py

import logging
from typing import List, Optional, Tuple
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud.doctrack import get_document_by_rsn
from app.db.remote_session import RemoteSessionLocal
from app.db.session import SessionLocal
from app.models.checklist import Checklist, ChecklistItem

logger = logging.getLogger(__name__)


class DuplicateDtnError(Exception):
    """The DTN is already in this checklist."""


def create_checklist(db: Session, username: str) -> Checklist:
    checklist = Checklist(created_by=username)
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    return checklist


def list_checklists(db: Session, limit: int = 50) -> List[dict]:
    rows = (
        db.query(Checklist, func.count(ChecklistItem.id))
        .outerjoin(
            ChecklistItem,
            and_(ChecklistItem.checklist_id == Checklist.id, ChecklistItem.is_removed == 0),
        )
        .filter(Checklist.is_deleted == 0)
        .group_by(Checklist.id)
        .order_by(Checklist.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": c.id, "created_by": c.created_by, "created_at": c.created_at, "label": c.label, "item_count": count}
        for c, count in rows
    ]


def get_checklist(db: Session, checklist_id: int) -> Optional[Checklist]:
    """Active (not deleted) checklist only."""
    return (
        db.query(Checklist)
        .filter(Checklist.id == checklist_id, Checklist.is_deleted == 0)
        .first()
    )


def update_label(db: Session, checklist_id: int, label: Optional[str]) -> Optional[Checklist]:
    checklist = get_checklist(db, checklist_id)
    if not checklist:
        return None
    checklist.label = label
    db.commit()
    db.refresh(checklist)
    return checklist


def add_item(db: Session, checklist_id: int, dtn: str, username: str) -> ChecklistItem:
    item = ChecklistItem(checklist_id=checklist_id, dtn=dtn, inserted_by=username)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateDtnError(dtn)
    db.refresh(item)
    return item


def remove_item(db: Session, checklist_id: int, item_id: int, username: str) -> bool:
    """Soft remove one DTN — it moves to the checklist's Bin."""
    item = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.id == item_id,
            ChecklistItem.checklist_id == checklist_id,
            ChecklistItem.is_removed == 0,
        )
        .first()
    )
    if not item:
        return False
    item.is_removed = 1
    item.removed_by = username
    item.removed_at = func.now()
    db.commit()
    return True


def list_bin(db: Session, checklist_id: int) -> List[ChecklistItem]:
    return (
        db.query(ChecklistItem)
        .filter(ChecklistItem.checklist_id == checklist_id, ChecklistItem.is_removed == 1)
        .order_by(ChecklistItem.removed_at.desc(), ChecklistItem.id.desc())
        .all()
    )


# ── DTN subject from FIS ───────────────────────────────────────────────────────

def lookup_fis_subject(dtn: str) -> Tuple[Optional[str], str]:
    """Look the DTN up in FIS — the same query as GET /api/doctrack/?rsn=
    (crud.doctrack.get_document_by_rsn). Returns (subject, status) with
    status "found", "not_found", or "error" (FIS couldn't be reached)."""
    remote = RemoteSessionLocal()
    try:
        rows = get_document_by_rsn(remote, dtn)
    except Exception as e:  # noqa: BLE001 — FIS down/slow must never break the checklist
        # One line, not a full traceback — when FIS is down this fires per DTN.
        logger.warning("FIS subject lookup failed for DTN %s: %s", dtn, str(e).splitlines()[0][:200])
        return None, "error"
    finally:
        remote.close()
    if not rows:
        return None, "not_found"
    return (rows[0].get("subject") or "").strip(), "found"


def _save_subject(db: Session, item: ChecklistItem, subject: Optional[str], status: str) -> None:
    item.subject = subject
    item.subject_status = status
    db.commit()


def fill_subject_in_background(item_id: int, dtn: str) -> None:
    """Runs after the insert's response is sent (FastAPI BackgroundTasks), so
    a slow FIS never holds up the insert. Uses its own DB session because the
    request's session is closed by then."""
    subject, status = lookup_fis_subject(dtn)
    db = SessionLocal()
    try:
        item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
        if item:
            _save_subject(db, item, subject, status)
    finally:
        db.close()


def refresh_subjects(db: Session, checklist_id: int) -> int:
    """Retry the lookup for this checklist's DTNs still pending or failed.
    Stops at the first "FIS unreachable" so a down FIS costs one timeout,
    not one per DTN. Returns how many were updated to found/not_found."""
    items = (
        db.query(ChecklistItem)
        .filter(
            ChecklistItem.checklist_id == checklist_id,
            ChecklistItem.is_removed == 0,
            ChecklistItem.subject_status.in_(("pending", "error")),
        )
        .order_by(ChecklistItem.id)
        .all()
    )
    updated = 0
    for item in items:
        subject, status = lookup_fis_subject(item.dtn)
        if status == "error":
            for rest in items[items.index(item):]:
                rest.subject_status = "error"
            db.commit()
            break
        _save_subject(db, item, subject, status)
        updated += 1
    return updated


def soft_delete_checklist(db: Session, checklist_id: int, username: str) -> bool:
    checklist = get_checklist(db, checklist_id)
    if not checklist:
        return False
    checklist.is_deleted = 1
    checklist.deleted_at = func.now()
    checklist.deleted_by = username
    db.commit()
    return True
