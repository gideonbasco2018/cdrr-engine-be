"""
CRUD Operations for User
Database operations for user authentication and management
UPDATED: Uses UserGroup association table (many-to-many)
New users are created as INACTIVE by default
"""

from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.user import User, UserRole
from app.models.group import Group
from app.models.user_groups import UserGroup
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


# ======================================================
# BASIC GETTERS
# ======================================================

def get_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


# ======================================================
# GROUP-BASED QUERIES
# ======================================================

def get_users_by_group(db: Session, group_id: int) -> List[User]:
    """
    Get all ACTIVE users belonging to a specific group
    """
    return (
        db.query(User)
        .join(UserGroup)
        .filter(
            UserGroup.group_id == group_id,
            User.is_active == True
        )
        .order_by(User.first_name, User.surname)
        .all()
    )


# ======================================================
# CREATE USER
# ======================================================

def create(db: Session, user_in: UserCreate) -> User:
    """
    Create new user and assign group(s)

    ⚠️ New users are INACTIVE by default
    """

    # ----------------------------------
    # Resolve role
    # ----------------------------------
    role = UserRole.USER
    if hasattr(user_in, "role") and user_in.role:
        role = (
            UserRole[user_in.role.upper()]
            if isinstance(user_in.role, str)
            else user_in.role
        )

    # ----------------------------------
    # Create user
    # ----------------------------------
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        surname=user_in.surname,
        position=getattr(user_in, "position", None),
        role=role,
        is_active=False,  # 🔒 inactive by default
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # ----------------------------------
    # Assign group
    # ----------------------------------
    if hasattr(user_in, "group_id") and user_in.group_id:
        group = db.query(Group).filter(Group.id == user_in.group_id).first()
    else:
        # Default "Users" group
        group = db.query(Group).filter(Group.name == "Users").first()
        if not group:
            group = Group(name="Users")
            db.add(group)
            db.commit()
            db.refresh(group)

    db.add(UserGroup(user_id=db_user.id, group_id=group.id))
    db.commit()
    db.refresh(db_user)

    return db_user


# ======================================================
# UPDATE USER
# ======================================================

def update(db: Session, user_id: int, user_in: UserUpdate) -> Optional[User]:
    db_user = get_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_in.dict(exclude_unset=True)

    # Handle password
    if "password" in update_data:
        db_user.hashed_password = get_password_hash(update_data.pop("password"))

    # Handle group update
    if "group_id" in update_data:
        new_group_id = update_data.pop("group_id")

        # remove old group links
        db.query(UserGroup).filter(UserGroup.user_id == db_user.id).delete()

        # add new group link
        db.add(UserGroup(user_id=db_user.id, group_id=new_group_id))

    # Update remaining fields
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


# ======================================================
# AUTHENTICATION
# ======================================================

def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    user = get_by_username(db, username)

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user


def is_active(user: User) -> bool:
    return user.is_active


# ======================================================
# ADMIN FUNCTIONS
# ======================================================

def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def get_pending_users(db: Session) -> List[User]:
    return (
        db.query(User)
        .filter(User.is_active == False)
        .order_by(User.created_at.desc())
        .all()
    )


def get_active_users(db: Session) -> List[User]:
    return (
        db.query(User)
        .filter(User.is_active == True)
        .order_by(User.first_name, User.surname)
        .all()
    )


def activate_user(db: Session, user_id: int) -> Optional[User]:
    user = get_by_id(db, user_id)
    if not user:
        return None

    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int) -> Optional[User]:
    user = get_by_id(db, user_id)
    if not user:
        return None

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
