"""
CRUD Operations for User
Database operations for user authentication and management
"""
from sqlalchemy.orm import Session
from typing import Optional

from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


def get_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get user by ID
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Optional[User]: User if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def get_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get user by email
    
    Args:
        db: Database session
        email: User email
        
    Returns:
        Optional[User]: User if found, None otherwise
    """
    return db.query(User).filter(User.email == email).first()


def get_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get user by username
    
    Args:
        db: Database session
        username: Username
        
    Returns:
        Optional[User]: User if found, None otherwise
    """
    return db.query(User).filter(User.username == username).first()


def create(db: Session, user_in: UserCreate) -> User:
    """
    Create new user
    
    Args:
        db: Database session
        user_in: User creation schema
        
    Returns:
        User: Created user
    """
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        surname=user_in.surname,
        position=user_in.position,
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

def update(db: Session, user_id: int, user_in: UserUpdate) -> Optional[User]:
    """
    Update user information
    
    Args:
        db: Database session
        user_id: User ID
        user_in: User update schema
        
    Returns:
        Optional[User]: Updated user if found, None otherwise
    """
    db_user = get_by_id(db, user_id)
    if not db_user:
        return None

    update_data = user_in.dict(exclude_unset=True)
    
    # Handle password separately - hash it before storing
    if 'password' in update_data:
        hashed_password = get_password_hash(update_data['password'])
        setattr(db_user, 'hashed_password', hashed_password)
        del update_data['password']  # Remove plain password from update_data
    
    # Update other fields
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    
    return db_user


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username and password
    
    Args:
        db: Database session
        username: Username
        password: Plain text password
        
    Returns:
        Optional[User]: User if authentication successful, None otherwise
    """
    user = get_by_username(db, username)
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    if not user.is_active:
        return None
    
    return user


def is_active(user: User) -> bool:
    """
    Check if user is active
    
    Args:
        user: User object
        
    Returns:
        bool: True if active, False otherwise
    """
    return user.is_active