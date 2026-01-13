"""
Authentication Routes
Login, registration, and user management endpoints
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import user as crud_user
from app.schemas.auth import Token, UserCreate, UserResponse, LoginResponse, UserUpdate
from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.user import User

router = APIRouter(
    prefix="/api/routes/auth",
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
    
    Returns JWT access token valid for 30 minutes
    
    - **username**: Your username
    - **password**: Your password
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
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
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
