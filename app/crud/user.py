"""
CRUD Operations for User
Database operations for user authentication and management
"""
from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.user import User, UserRole
from app.models.group import Group
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


def get_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

# ✅ NEW: Get users by group
def get_users_by_group(db: Session, group_id: int) -> List[User]:
    """
    Get all active users from a specific group
    
    Returns list of users who can be assigned to tasks.
    Ordered by name for better UX in dropdowns.
    """
    return db.query(User).filter(
        User.group_id == group_id,
        User.is_active == True
    ).order_by(
        User.first_name, 
        User.surname
    ).all()

def create(db: Session, user_in: UserCreate) -> User:
    """
    Create new user with default group if not provided.
    """
    # Handle group_id - assign default "Users" group if not provided
    if user_in.group_id:
        group_id = user_in.group_id
    else:
        # Get or create default "Users" group
        default_group = db.query(Group).filter_by(name="Users").first()
        if not default_group:
            default_group = Group(name="Users")
            db.add(default_group)
            db.commit()
            db.refresh(default_group)
        group_id = default_group.id

    # Handle role - convert from schema enum to model enum
    role = UserRole.USER  # default
    if user_in.role:
        # Convert string to UserRole enum
        role = UserRole[user_in.role.value.upper()]

    # Create user
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        surname=user_in.surname,
        position=user_in.position,
        role=role,
        group_id=group_id
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update(db: Session, user_id: int, user_in: UserUpdate) -> Optional[User]:
    """Update user information"""
    db_user = get_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_in.dict(exclude_unset=True)
    
    # Handle password separately - hash it before storing
    if 'password' in update_data:
        hashed_password = get_password_hash(update_data['password'])
        setattr(db_user, 'hashed_password', hashed_password)
        del update_data['password']
    
    # Update other fields
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    
    return db_user


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user = get_by_username(db, username)
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    return user


def is_active(user: User) -> bool:
    """Check if user is active"""
    return user.is_active