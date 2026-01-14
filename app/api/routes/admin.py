# app/api/routes/admin.py
"""
Admin Routes
User management and admin-only endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.user import User
from app.schemas.auth import UserResponse
from app.crud import user as crud_user

router = APIRouter(
    prefix="/api/routes/admin",
    tags=["Admin"]
)

@router.get("/users", response_model=List[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get all users - Admin/SuperAdmin only"""
    users = crud_user.get_all(db)
    return users

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    """Delete user - SuperAdmin only"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    crud_user.delete(db, user_id)
    return {"message": "User deleted successfully"}