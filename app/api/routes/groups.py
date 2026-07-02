# app/api/routes/groups.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User, UserRole
from app.crud import groups as crud_group
from app.crud import user as crud_user
from app.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupResponse,
    GroupUserAssign,
)

router = APIRouter(
    prefix="/api/groups",
    tags=["Group Management"],
)


# ========================================
# HELPERS
# ========================================

def require_admin(current_user: User):
    """Shared guard — Admin or SuperAdmin only"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage groups",
        )


# ========================================
# GROUP CRUD
# ========================================

@router.get("", response_model=List[GroupResponse])
def get_all_groups(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get all groups. Includes user_count (any authenticated user can view)."""
    groups = crud_group.get_all(db)

    # ✅ Attach user_count dynamically
    result = []
    for g in groups:
        result.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "user_count": len(g.users),
        })
    return result


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a single group by ID"""
    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )
    return group


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    group_in: GroupCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new group — Admin/SuperAdmin only"""
    require_admin(current_user)

    # Check duplicate name
    if crud_group.get_by_name(db, group_in.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Group name "{group_in.name}" already exists',
        )

    group = crud_group.create(db, group_in)
    return group


@router.put("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    group_in: GroupUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update group name/description — Admin/SuperAdmin only"""
    require_admin(current_user)

    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )

    # If name changed, check duplicate
    if group_in.name and group_in.name != group.name:
        if crud_group.get_by_name(db, group_in.name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Group name "{group_in.name}" already exists',
            )

    updated = crud_group.update(db, group_id, group_in)
    return updated


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a group — SuperAdmin only. CASCADE auto-removes user_groups rows."""
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SuperAdmin can delete groups",
        )

    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )

    crud_group.delete(db, group_id)


# ========================================
# USER <-> GROUP ASSIGNMENT
# ========================================

@router.get("/{group_id}/users", response_model=List[dict])
def get_group_users(
    group_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get all users in a specific group"""
    require_admin(current_user)

    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )

    users = crud_group.get_group_users(db, group_id)

    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "first_name": u.first_name,
            "surname": u.surname,
            "role": u.role.value,
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.post("/{group_id}/users", status_code=status.HTTP_200_OK)
def assign_user_to_group(
    group_id: int,
    body: GroupUserAssign,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Assign a user to a group — Admin/SuperAdmin only"""
    require_admin(current_user)

    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )

    user = crud_user.get_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {body.user_id} not found",
        )

    # Already in group?
    if crud_group.get_user_group_link(db, body.user_id, group_id):
        return {"success": False, "message": "User is already in this group"}

    crud_group.assign_user(db, body.user_id, group_id)

    return {"success": True, "message": f"User '{user.username}' added to group '{group.name}'"}


@router.delete("/{group_id}/users/{user_id}", status_code=status.HTTP_200_OK)
def remove_user_from_group(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove a user from a group — Admin/SuperAdmin only"""
    require_admin(current_user)

    group = crud_group.get_by_id(db, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found",
        )

    user = crud_user.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Not in group?
    if not crud_group.get_user_group_link(db, user_id, group_id):
        return {"success": False, "message": "User is not in this group"}

    crud_group.remove_user(db, user_id, group_id)

    return {"success": True, "message": f"User '{user.username}' removed from group '{group.name}'"}