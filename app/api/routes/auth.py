"""
Authentication Routes - COMPLETE
Login, registration, and user management endpoints
UPDATED: Handles inactive users with proper error messages
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import user as crud_user
from app.schemas.auth import Token, UserCreate, UserResponse, LoginResponse, UserUpdate
from app.core.security import create_access_token, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User, UserRole

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user
    
    ⚠️ New users are created as INACTIVE and require admin approval
    
    - **email**: User's email address (must be unique)
    - **username**: Username (must be unique)
    - **password**: Password (minimum 8 characters)
    - **first_name**: User's first name
    - **surname**: User's surname
    - **position**: Optional position/role
    """
    # Check if email already exists
    existing_user = crud_user.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_user = crud_user.get_by_username(db, username=user_in.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user (will be inactive by default)
    user = crud_user.create(db, user_in=user_in)
    
    return user


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with username and password
    
    ⚠️ Only ACTIVE users can log in
    """
    # First check if user exists
    user = crud_user.get_by_username(db, username=form_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password before checking active status
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active AFTER verifying password
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval. Please wait for admin confirmation or contact support.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token WITH ROLE
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value
        },
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current logged in user information
    
    Requires valid JWT token in Authorization header
    """
    return current_user


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout current user
    
    Note: JWT tokens are stateless, so client should delete the token
    """
    return {
        "success": True,
        "message": "Successfully logged out. Please delete your token from client storage."
    }


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's information
    
    Requires valid JWT token in Authorization header
    """
    updated_user = crud_user.update(db, current_user.id, user_update)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return updated_user


# ========================================
# USER MANAGEMENT ENDPOINTS
# ========================================

@router.get("/users/group", response_model=List[UserResponse])
def get_group_users(
    group_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of ACTIVE users from a specific group
    
    Query Parameters:
    - **group_id**: (Optional) Specific group ID to get users from.
                    If not provided, returns users from current user's group.
    """
    target_group_id = group_id if group_id is not None else current_user.group_id
    
    users = crud_user.get_users_by_group(db, group_id=target_group_id)
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active users found in group {target_group_id}"
        )
    
    return users


@router.get("/users/group/{group_id}", response_model=List[UserResponse])
def get_users_by_specific_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of ACTIVE users from a specific group by group ID
    
    Returns only active users (is_active = True)
    """
    # Define allowed cross-group access
    allowed_access = False
    
    if group_id == current_user.group_id:
        allowed_access = True
    elif current_user.role in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        allowed_access = True
    elif current_user.group_id == 2 and group_id == 3:
        allowed_access = True
    elif current_user.group_id == 3 and group_id == 4:
        allowed_access = True
    elif current_user.group_id == 4 and group_id == 3:
        allowed_access = True
    
    if not allowed_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view users from other groups"
        )
    
    users = crud_user.get_users_by_group(db, group_id=group_id)
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active users found in group {group_id}"
        )
    
    return users


@router.get("/users/my-group", response_model=List[UserResponse])
def get_my_group_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of ACTIVE users from current user's group
    """
    users = crud_user.get_users_by_group(db, group_id=current_user.group_id)
    return users


# ========================================
# ADMIN-ONLY: USER APPROVAL ENDPOINTS
# ========================================

@router.get("/admin/users/pending", response_model=List[UserResponse])
def get_pending_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all users pending approval (is_active = False)
    
    🔒 ADMIN ONLY
    """
    # Check if user is admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view pending users"
        )
    
    pending_users = crud_user.get_pending_users(db)
    return pending_users


@router.post("/admin/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Activate a user account (approve registration)
    
    🔒 ADMIN ONLY
    """
    # Check if user is admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can activate users"
        )
    
    user = crud_user.activate_user(db, user_id=user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("/admin/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user account (suspend/ban user)
    
    🔒 ADMIN ONLY
    """
    # Check if user is admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can deactivate users"
        )
    
    # Prevent deactivating yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    
    user = crud_user.deactivate_user(db, user_id=user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/admin/users", response_model=List[UserResponse])
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all users (both active and inactive)
    
    🔒 ADMIN ONLY
    """
    # Check if user is admin
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view all users"
        )
    
    users = crud_user.get_all_users(db, skip=skip, limit=limit)
    return users