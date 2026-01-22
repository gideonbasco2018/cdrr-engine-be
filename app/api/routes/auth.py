"""
Authentication Routes
Login, registration, and user management endpoints
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
from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
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
    
    # Create new user
    user = crud_user.create(db, user_in=user_in)
    
    return user


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login with username and password
    """
    # Authenticate user
    user = crud_user.authenticate(
        db,
        username=form_data.username,
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token WITH ROLE
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value  # ADD THIS - include role in token
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

# ✅ UPDATED: Get users by group_id (with optional parameter)
@router.get("/users/group", response_model=List[UserResponse])
def get_group_users(
    group_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of active users from a specific group
    
    Query Parameters:
    - **group_id**: (Optional) Specific group ID to get users from.
                    If not provided, returns users from current user's group.
    
    Returns all users in the group who can be assigned as:
    - Deckers
    - Evaluators
    - Reviewers
    - etc.
    """
    # If no group_id provided, use current user's group
    target_group_id = group_id if group_id is not None else current_user.group_id
    
    # Optional: Check if user has permission to view other groups
    # Uncomment if you want to restrict access
    # if target_group_id != current_user.group_id and current_user.role != UserRole.ADMIN:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You don't have permission to view users from other groups"
    #     )
    
    users = crud_user.get_users_by_group(db, group_id=target_group_id)
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No users found in group {target_group_id}"
        )
    
    return users

# ✅ ALTERNATIVE: More RESTful approach with path parameter
@router.get("/users/group/{group_id}", response_model=List[UserResponse])
def get_users_by_specific_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of active users from a specific group by group ID
    
    Path Parameters:
    - **group_id**: The group ID to fetch users from
    
    Permission Rules:
    - Users can view their own group
    - Admins can view all groups
    - Deckers (group 2) can view Evaluators (group 3)
    - Evaluators (group 3) can view Checkers (group 4)
    - Checkers (group 4) can view Evaluators (group 3)
    """
    # Define allowed cross-group access
    allowed_access = False
    
    # 1. User viewing their own group
    if group_id == current_user.group_id:
        allowed_access = True
    
    # 2. Admin can view all groups
    elif current_user.role == UserRole.ADMIN:
        allowed_access = True
    
    # 3. Decker (group 2) can view Evaluator (group 3)
    elif current_user.group_id == 2 and group_id == 3:
        allowed_access = True
    
    # 4. Evaluator (group 3) can view Checker (group 4)
    elif current_user.group_id == 3 and group_id == 4:
        allowed_access = True
    
    # 5. Checker (group 4) can view Evaluator (group 3) - for returning tasks
    elif current_user.group_id == 4 and group_id == 3:
        allowed_access = True
    
    # Check permission
    if not allowed_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view users from other groups"
        )
    
    users = crud_user.get_users_by_group(db, group_id=group_id)
    
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No users found in group {group_id}"
        )
    
    return users

# ✅ Get current user's group users (shortcut)
@router.get("/users/my-group", response_model=List[UserResponse])
def get_my_group_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get list of active users from current user's group
    """
    users = crud_user.get_users_by_group(db, group_id=current_user.group_id)
    return users