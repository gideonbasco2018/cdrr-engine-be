# ============================================================
# FILE: app/crud/menu_permissions.py
# ============================================================

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from fastapi import HTTPException

from app.models.menu_permissions import MenuItem  # ✅ PLURAL
from app.models.group import Group
from app.schemas.menu_permissions import MenuItemCreate, MenuItemUpdate  # ✅ PLURAL


def get_all_menu_items(db: Session) -> List[MenuItem]:
    """Get all menu items ordered by order field"""
    return db.query(MenuItem).order_by(MenuItem.order, MenuItem.id).all()


def get_all_menu_permissions(db: Session) -> List[Dict[str, Any]]:
    """Get all menu items with their group permissions"""
    menu_items = get_all_menu_items(db)
    
    result = []
    for item in menu_items:
        result.append({
            "id": item.id,
            "menu_id": item.menu_id,
            "name": item.name,
            "path": item.path,
            "icon": item.icon,
            "parent_id": item.parent_id,
            "order": item.order,
            "group_ids": [group.id for group in item.groups],
            "groups": [{"id": group.id, "name": group.name} for group in item.groups]
        })
    
    return result


def get_menu_item_by_id(db: Session, menu_item_id: int) -> Optional[MenuItem]:
    """Get a menu item by ID"""
    return db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()


def get_menu_item_by_menu_id(db: Session, menu_id: str) -> Optional[MenuItem]:
    """Get a specific menu item by menu_id"""
    return db.query(MenuItem).filter(MenuItem.menu_id == menu_id).first()


def get_menu_item_permissions(db: Session, menu_id: str) -> Optional[Dict[str, Any]]:
    """Get permissions for a specific menu item"""
    menu_item = get_menu_item_by_menu_id(db, menu_id)
    
    if not menu_item:
        return None
    
    return {
        "id": menu_item.id,
        "menu_id": menu_item.menu_id,
        "name": menu_item.name,
        "path": menu_item.path,
        "icon": menu_item.icon,
        "parent_id": menu_item.parent_id,
        "order": menu_item.order,
        "group_ids": [group.id for group in menu_item.groups],
        "groups": [{"id": group.id, "name": group.name} for group in menu_item.groups]
    }


def create_menu_item(db: Session, menu_item: MenuItemCreate, group_ids: Optional[List[int]] = None) -> MenuItem:
    """Create a new menu item with optional group permissions"""
    # Check if menu_id already exists
    existing = get_menu_item_by_menu_id(db, menu_item.menu_id)
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Menu item with menu_id '{menu_item.menu_id}' already exists"
        )
    
    # Create menu item
    db_menu_item = MenuItem(
        menu_id=menu_item.menu_id,
        name=menu_item.name,
        path=menu_item.path,
        icon=menu_item.icon,
        parent_id=menu_item.parent_id,
        order=menu_item.order
    )
    
    # Add groups if provided with validation
    if group_ids:
        groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
        if len(groups) != len(group_ids):
            found_ids = {g.id for g in groups}
            missing_ids = set(group_ids) - found_ids
            raise HTTPException(
                status_code=404, 
                detail=f"Groups not found: {list(missing_ids)}"
            )
        db_menu_item.groups = groups
    
    try:
        db.add(db_menu_item)
        db.commit()
        db.refresh(db_menu_item)
        return db_menu_item
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail=f"Database integrity error: {str(e)}"
        )


def update_menu_item(db: Session, menu_id: str, menu_update: MenuItemUpdate) -> Optional[MenuItem]:
    """Update menu item details (not permissions)"""
    menu_item = get_menu_item_by_menu_id(db, menu_id)
    
    if not menu_item:
        return None
    
    # Update only provided fields
    update_data = menu_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(menu_item, field, value)
    
    try:
        db.commit()
        db.refresh(menu_item)
        return menu_item
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail=f"Database integrity error: {str(e)}"
        )


def update_menu_permissions(db: Session, menu_id: str, group_ids: List[int]) -> Optional[Dict[str, Any]]:
    """Update group permissions for a specific menu item"""
    menu_item = get_menu_item_by_menu_id(db, menu_id)
    
    if not menu_item:
        return None
    
    # Validate that all groups exist
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all()
    
    if len(groups) != len(group_ids):
        found_ids = {g.id for g in groups}
        missing_ids = set(group_ids) - found_ids
        raise HTTPException(
            status_code=404, 
            detail=f"Groups not found: {list(missing_ids)}"
        )
    
    # Update the menu item's groups
    menu_item.groups = groups
    
    try:
        db.commit()
        db.refresh(menu_item)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail=f"Database integrity error: {str(e)}"
        )
    
    return {
        "id": menu_item.id,
        "menu_id": menu_item.menu_id,
        "name": menu_item.name,
        "path": menu_item.path,
        "icon": menu_item.icon,
        "parent_id": menu_item.parent_id,
        "order": menu_item.order,
        "group_ids": [group.id for group in menu_item.groups],
        "groups": [{"id": group.id, "name": group.name} for group in menu_item.groups]
    }


def delete_menu_item(db: Session, menu_id: str) -> bool:
    """Delete a menu item"""
    menu_item = get_menu_item_by_menu_id(db, menu_id)
    
    if not menu_item:
        return False
    
    try:
        db.delete(menu_item)
        db.commit()
        return True
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete menu item: {str(e)}"
        )


def get_user_accessible_menus(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all menu items accessible by a specific user based on their group memberships.
    This is CRITICAL for frontend to show only menus the user can access.
    """
    from app.models.user_groups import UserGroup
    
    # Get user's groups
    user_groups = db.query(UserGroup).filter(UserGroup.user_id == user_id).all()
    group_ids = [ug.group_id for ug in user_groups]
    
    if not group_ids:
        return []
    
    # Get all menu items accessible by these groups
    menu_items = db.query(MenuItem).join(
        MenuItem.groups
    ).filter(
        Group.id.in_(group_ids)
    ).distinct().order_by(MenuItem.order, MenuItem.id).all()
    
    result = []
    for item in menu_items:
        result.append({
            "id": item.id,
            "menu_id": item.menu_id,
            "name": item.name,
            "path": item.path,
            "icon": item.icon,
            "parent_id": item.parent_id,
            "order": item.order
        })
    
    return result