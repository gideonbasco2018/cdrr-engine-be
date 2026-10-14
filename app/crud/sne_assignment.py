# app/crud/sne_assignment.py
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_groups import UserGroup
from app.models.sne_assignment import SneGenericAssignment as SneAssign
from app.models.application_logs import ApplicationLogs  # adjust path if different

SE_GROUP_ID = 13  # same as GROUP_IDS.SE in the frontend


# ── Read ──────────────────────────────────────────────────────────────
def get_sne_users(db: Session, user_id: Optional[int] = None) -> List[User]:
    """Active members of the S&E group."""
    q = (
        db.query(User)
        .join(UserGroup, UserGroup.user_id == User.id)
        .filter(UserGroup.group_id == SE_GROUP_ID, User.is_active.is_(True))
    )
    if user_id is not None:
        q = q.filter(User.id == user_id)
    return q.order_by(User.username).all()


def get(db: Session, assignment_id: int) -> Optional[SneAssign]:
    return db.query(SneAssign).filter(SneAssign.id == assignment_id).first()


def get_by_user_keyword(db: Session, user_id: int, keyword: str) -> Optional[SneAssign]:
    return (
        db.query(SneAssign)
        .filter(SneAssign.user_id == user_id, SneAssign.keyword == keyword)
        .first()
    )


def get_all(db: Session, user_id: Optional[int] = None) -> List[SneAssign]:
    q = db.query(SneAssign)
    if user_id is not None:
        q = q.filter(SneAssign.user_id == user_id)
    return q.order_by(SneAssign.user_id, SneAssign.keyword).all()


def get_keywords_by_users(db: Session, user_ids: List[int]) -> Dict[int, List[str]]:
    if not user_ids:
        return {}
    rows = (
        db.query(SneAssign.user_id, SneAssign.keyword)
        .filter(SneAssign.user_id.in_(user_ids))
        .order_by(SneAssign.keyword)
        .all()
    )
    out: Dict[int, List[str]] = {}
    for uid, kw in rows:
        out.setdefault(uid, []).append(kw)
    return out


def get_active_keyword_pairs(db: Session) -> List[Tuple[str, int]]:
    """(keyword, user_id) for active S&E members only."""
    return (
        db.query(SneAssign.keyword, SneAssign.user_id)
        .join(User, User.id == SneAssign.user_id)
        .join(UserGroup, UserGroup.user_id == User.id)
        .filter(UserGroup.group_id == SE_GROUP_ID, User.is_active.is_(True))
        .all()
    )


def get_in_progress_counts(db: Session, user_ids: List[int]) -> Dict[int, int]:
    """Number of S&E tasks currently IN PROGRESS per user."""
    load = {uid: 0 for uid in user_ids}
    if not user_ids:
        return load
    rows = (
        db.query(ApplicationLogs.user_id, func.count())
        .filter(
            ApplicationLogs.application_step == "S&E",
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.user_id.in_(user_ids),
        )
        .group_by(ApplicationLogs.user_id)
        .all()
    )
    load.update({uid: cnt for uid, cnt in rows})
    return load


# ── Create ────────────────────────────────────────────────────────────
def create(db: Session, user_id: int, keyword: str) -> SneAssign:
    obj = SneAssign(user_id=user_id, keyword=keyword)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── Update (replace all keywords of one user) ─────────────────────────
def replace_for_user(db: Session, user_id: int, keywords: List[str]) -> List[SneAssign]:
    db.query(SneAssign).filter(SneAssign.user_id == user_id).delete(
        synchronize_session=False
    )
    db.add_all([SneAssign(user_id=user_id, keyword=k) for k in keywords])
    db.commit()
    return get_all(db, user_id)


# ── Delete ────────────────────────────────────────────────────────────
def delete(db: Session, assignment_id: int) -> bool:
    obj = get(db, assignment_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def get_in_progress_by_step(
    db: Session, user_ids: List[int]
) -> Dict[int, Dict[str, int]]:
    """{ user_id: { application_step: count } } for IN PROGRESS tasks."""
    if not user_ids:
        return {}
    rows = (
        db.query(
            ApplicationLogs.user_id,
            ApplicationLogs.application_step,
            func.count(),
        )
        .filter(
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.user_id.in_(user_ids),
        )
        .group_by(ApplicationLogs.user_id, ApplicationLogs.application_step)
        .all()
    )
    out: Dict[int, Dict[str, int]] = {}
    for uid, step, cnt in rows:
        out.setdefault(uid, {})[step or "—"] = cnt
    return out
