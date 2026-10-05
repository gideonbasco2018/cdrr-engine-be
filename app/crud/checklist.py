# app/crud/checklist.py

from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.checklist import Checklist, ChecklistItem


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
        .outerjoin(ChecklistItem, ChecklistItem.checklist_id == Checklist.id)
        .group_by(Checklist.id)
        .order_by(Checklist.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": c.id, "created_by": c.created_by, "created_at": c.created_at, "item_count": count}
        for c, count in rows
    ]


def get_checklist(db: Session, checklist_id: int) -> Optional[Checklist]:
    return db.query(Checklist).filter(Checklist.id == checklist_id).first()


def add_item(db: Session, checklist_id: int, dtn: str, username: str) -> ChecklistItem:
    item = ChecklistItem(checklist_id=checklist_id, dtn=dtn, scanned_by=username)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateDtnError(dtn)
    db.refresh(item)
    return item


def delete_item(db: Session, checklist_id: int, item_id: int) -> bool:
    item = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def delete_checklist(db: Session, checklist_id: int) -> bool:
    checklist = get_checklist(db, checklist_id)
    if not checklist:
        return False
    db.delete(checklist)
    db.commit()
    return True
