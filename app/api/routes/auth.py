# app/api/routes/auth.py

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from app.services.google_drive import (
    upload_file_to_drive,
    get_or_create_folder_path,
    delete_file_from_drive,
)

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import user as crud_user
from app.schemas.auth import (
    Token,
    UserCreate,
    UserResponse,
    LoginResponse,
    UserUpdate,
    AdminUserUpdate,
)
from app.core.security import (
    create_access_token,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.models.user import User, UserRole
from pydantic import BaseModel, EmailStr

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

PROFILE_PIC_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
PROFILE_PIC_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# ========================================
# AUTHENTICATION
# ========================================


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user (inactive by default)
    """
    if crud_user.get_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if crud_user.get_by_username(db, username=user_in.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    user = crud_user.create(db, user_in=user_in)
    return user


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login (ACTIVE users only)
    """
    user = crud_user.get_by_username(db, username=form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending approval. Please contact an administrator.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value,
        },
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    return current_user


@router.post("/me/profile-picture", response_model=UserResponse)
async def upload_my_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload/replace the CURRENT user's own profile picture."""
    if file.content_type not in PROFILE_PIC_ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only JPG, PNG, GIF, or WEBP images are allowed.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > PROFILE_PIC_MAX_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit.")

    try:
        folder_id = get_or_create_folder_path(
            "Profile Pictures", current_user.username, []
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to prepare Drive folder: {exc}"
        )

    existing_file_id = current_user.profile_picture_drive_id

    try:
        drive_result = upload_file_to_drive(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            folder_id=folder_id,
            existing_file_id=existing_file_id,
        )
        direct_url = (
            f"https://drive.google.com/thumbnail?id={drive_result['file_id']}&sz=w200"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Google Drive upload failed: {exc}"
        )

    updated_user = crud_user.update_profile_picture(
        db,
        user_id=current_user.id,
        profile_picture_url=direct_url,
        profile_picture_drive_id=drive_result["file_id"],
    )

    return updated_user


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_active_user),
):
    return {
        "success": True,
        "message": "Successfully logged out. Please delete your token from client storage.",
    }


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    updated_user = crud_user.update(db, current_user.id, user_update)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return updated_user


# ========================================
# GROUP-BASED USER QUERIES
# ========================================


@router.get("/users/group", response_model=List[UserResponse])
def get_group_users(
    group_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get ACTIVE users from a group.
    Defaults to current user's primary group.
    """
    if group_id is not None:
        target_group_id = group_id
    else:
        if not current_user.group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user has no group assigned",
            )
        target_group_id = current_user.group_id

    users = crud_user.get_users_by_group(db, group_id=target_group_id)

    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active users found in group {target_group_id}",
        )

    return users


@router.get("/users/group/{group_id}", response_model=List[UserResponse])
def get_users_by_specific_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get ACTIVE users from a specific group.
    Any authenticated user can query — needed for workflow assignment.
    """
    users = crud_user.get_users_by_group(db, group_id=group_id)

    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active users found in group {group_id}",
        )

    return users


@router.get("/users/my-group", response_model=List[UserResponse])
def get_my_group_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get ACTIVE users from current user's primary group
    """
    if not current_user.group_id:
        return []

    return crud_user.get_users_by_group(db, group_id=current_user.group_id)


# ========================================
# ADMIN ONLY
# ========================================


@router.get("/admin/users/pending", response_model=List[UserResponse])
def get_pending_users(
    skip: int = 0,
    limit: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all pending (inactive) users.
    Supports optional pagination via skip and limit query params.
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view pending users",
        )

    return crud_user.get_pending_users(db, skip=skip, limit=limit)


@router.post("/admin/users/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can activate users",
        )

    user = crud_user.activate_user(db, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.post("/admin/users/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can deactivate users",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user = crud_user.deactivate_user(db, user_id=user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


class PasswordResetRequest(BaseModel):
    new_password: str


@router.post("/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    password_data: PasswordResetRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Manually reset a user's password
    Admin/SuperAdmin only
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can reset passwords",
        )

    user = crud_user.reset_user_password(
        db, user_id=user_id, new_password=password_data.new_password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "success": True,
        "message": f"Password for {user.username} has been reset successfully.",
    }


@router.get("/admin/users", response_model=List[UserResponse])
def get_all_users(
    skip: int = 0,
    limit: Optional[int] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all users.
    Supports optional pagination via skip and limit query params.
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view all users",
        )

    return crud_user.get_all_users(db, skip=skip, limit=limit)


@router.patch("/admin/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: int,
    user_update: AdminUserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update another user's details (Admin/SuperAdmin only)
    Can update: username, email, role, first_name, surname, position, group_id
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update user details",
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /api/auth/me to update your own profile",
        )

    target_user = crud_user.get_by_id(db, user_id=user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user_update.username and user_update.username != target_user.username:
        existing = crud_user.get_by_username(db, username=user_update.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    if user_update.email and user_update.email != target_user.email:
        existing = crud_user.get_by_email(db, email=user_update.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    update_dict = user_update.dict(exclude_unset=True)
    if "role" in update_dict:
        try:
            update_dict["role"] = UserRole[update_dict["role"].upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be one of: User, Admin, SuperAdmin",
            )

    updated_user = crud_user.admin_update_user(
        db, user_id=user_id, update_data=update_dict
    )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return updated_user


@router.post("/admin/users/{user_id}/profile-picture", response_model=UserResponse)
async def upload_profile_picture(
    user_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Upload/replace a user's profile picture — stored on Google Drive."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update profile pictures",
        )

    target_user = crud_user.get_by_id(db, user_id=user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if file.content_type not in PROFILE_PIC_ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Only JPG, PNG, GIF, or WEBP images are allowed.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > PROFILE_PIC_MAX_SIZE:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit.")

    try:
        folder_id = get_or_create_folder_path(
            "Profile Pictures", target_user.username, []
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to prepare Drive folder: {exc}"
        )

    # Overwrite existing picture on Drive kung meron nang na-upload dati
    existing_file_id = target_user.profile_picture_drive_id
    try:
        drive_result = upload_file_to_drive(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            folder_id=folder_id,
            existing_file_id=existing_file_id,
        )
        direct_url = (
            f"https://drive.google.com/thumbnail?id={drive_result['file_id']}&sz=w200"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Google Drive upload failed: {exc}"
        )

    updated_user = crud_user.update_profile_picture(
        db,
        user_id=user_id,
        profile_picture_url=direct_url,  # ⬅ ito yung binago, dating drive_result["file_url"]
        profile_picture_drive_id=drive_result["file_id"],
    )

    return updated_user
