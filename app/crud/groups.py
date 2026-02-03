"""
CRUD Operations for Group
Database operations for group management and user-group assignments
Uses UserGroup association table (many-to-many)
"""

from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.group import Group
from app.models.user import User
from app.models.user_groups import UserGroup
from app.schemas.group import GroupCreate, GroupUpdate


# ======================================================
# BASIC GETTERS
# ======================================================

def get_by_id(db: Session, group_id: int) -> Optional[Group]:
    return db.query(Group).filter(Group.id == group_id).first()


def get_by_name(db: Session, name: str) -> Optional[Group]:
    return db.query(Group).filter(Group.name == name).first()


def get_all(db: Session) -> List[Group]:
    return db.query(Group).order_by(Group.id).all()


# ======================================================
# CREATE / UPDATE / DELETE
# ======================================================

def create(db: Session, group_in: GroupCreate) -> Group:
    db_group = Group(
        name=group_in.name,
        description=group_in.description,
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


def update(db: Session, group_id: int, group_in: GroupUpdate) -> Optional[Group]:
    db_group = get_by_id(db, group_id)
    if not db_group:
        return None

    update_data = group_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_group, field, value)

    db.commit()
    db.refresh(db_group)
    return db_group


def delete(db: Session, group_id: int) -> bool:
    """
    Delete group.
    CASCADE on ForeignKey ang bahala sa pag-delete ng user_groups rows.
    """
    db_group = get_by_id(db, group_id)
    if not db_group:
        return False

    db.delete(db_group)
    db.commit()
    return True


# ======================================================
# USER <-> GROUP ASSIGNMENT
# ======================================================

def get_group_users(db: Session, group_id: int) -> List[User]:
    """Get all users in a specific group (active + inactive)"""
    return (
        db.query(User)
        .join(UserGroup)
        .filter(UserGroup.group_id == group_id)
        .order_by(User.first_name, User.surname)
        .all()
    )


def get_user_group_link(db: Session, user_id: int, group_id: int) -> Optional[UserGroup]:
    """Get the UserGroup association row — used for checking existence"""
    return (
        db.query(UserGroup)
        .filter(
            UserGroup.user_id == user_id,
            UserGroup.group_id == group_id,
        )
        .first()
    )


def assign_user(db: Session, user_id: int, group_id: int) -> UserGroup:
    """Create UserGroup association row"""
    link = UserGroup(user_id=user_id, group_id=group_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def remove_user(db: Session, user_id: int, group_id: int) -> bool:
    """Delete UserGroup association row"""
    link = get_user_group_link(db, user_id, group_id)
    if not link:
        return False

    db.delete(link)
    db.commit()
    return True