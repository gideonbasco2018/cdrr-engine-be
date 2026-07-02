# app/api/routes/menu_permissions.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_db, get_current_active_user  # ✅ Import auth dependency
from app.crud import menu_permissions as crud_menu
from app.schemas.menu_permissions import (
    MenuPermissionResponse,
    MenuPermissionUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    MenuItemListResponse
)

# Router with prefix, tags, and auth dependency
router = APIRouter(
    prefix="/api/menu-permissions",
    tags=["Menu Permissions"],
    dependencies=[Depends(get_current_active_user)]  # ✅ Requires authentication for ALL endpoints
)


@router.get("/", response_model=List[MenuPermissionResponse])
def get_menu_permissions(db: Session = Depends(get_db)):
    """
    Get all menu items with their group permissions.
    
    Returns:
        List of all menu items with their associated groups
    """
    return crud_menu.get_all_menu_permissions(db)


@router.get("/user/{user_id}", response_model=List[MenuItemListResponse])
def get_user_menus(user_id: int, db: Session = Depends(get_db)):
    """
    Get all menu items accessible by a specific user.
    
    This endpoint returns only the menus that the user has permission to access
    based on their group memberships. Use this in your frontend to build the navigation menu.
    
    Args:
        user_id: The ID of the user
    
    Returns:
        List of menu items the user can access
    """
    return crud_menu.get_user_accessible_menus(db, user_id)


@router.get("/{menu_id}", response_model=MenuPermissionResponse)
def get_menu_item_permissions(menu_id: str, db: Session = Depends(get_db)):
    """
    Get permissions for a specific menu item by menu_id.
    
    Args:
        menu_id: The unique identifier for the menu item (e.g., "dashboard", "for-decking")
    
    Returns:
        Menu item details with list of groups that have access
    """
    menu_item = crud_menu.get_menu_item_permissions(db, menu_id)
    
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item '{menu_id}' not found"
        )
    
    return menu_item


@router.post("/", response_model=MenuPermissionResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    menu_item: MenuItemCreate,
    group_ids: List[int] = [],
    db: Session = Depends(get_db)
):
    """
    Create a new menu item with optional group permissions.
    
    Args:
        menu_item: Menu item details (menu_id, name, path, icon, parent_id, order)
        group_ids: Optional list of group IDs that should have access to this menu
    
    Returns:
        Created menu item with permissions
    
    Example:
        POST /api/menu-permissions/
        {
            "menu_id": "analytics",
            "name": "Analytics",
            "path": "/analytics",
            "icon": "BarChart",
            "order": 11,
            "group_ids": [1, 2]
        }
    """
    db_menu_item = crud_menu.create_menu_item(db, menu_item, group_ids)
    return crud_menu.get_menu_item_permissions(db, db_menu_item.menu_id)


@router.put("/{menu_id}", response_model=MenuPermissionResponse)
def update_menu_item(
    menu_id: str,
    menu_update: MenuItemUpdate,
    db: Session = Depends(get_db)
):
    """
    Update menu item details (name, path, icon, order, parent_id).
    
    This does NOT update permissions. Use PUT /{menu_id}/permissions for that.
    
    Args:
        menu_id: The unique identifier for the menu item
        menu_update: Fields to update (only provided fields will be updated)
    
    Returns:
        Updated menu item with current permissions
    
    Example:
        PUT /api/menu-permissions/dashboard
        {
            "name": "Updated Dashboard",
            "order": 5
        }
    """
    updated_menu = crud_menu.update_menu_item(db, menu_id, menu_update)
    
    if not updated_menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item '{menu_id}' not found"
        )
    
    return crud_menu.get_menu_item_permissions(db, menu_id)


@router.put("/{menu_id}/permissions", response_model=MenuPermissionResponse)
def update_menu_permissions(
    menu_id: str,
    permission_update: MenuPermissionUpdate,
    db: Session = Depends(get_db)
):
    """
    Update group permissions for a specific menu item.
    
    This REPLACES all existing permissions with the new list of group IDs.
    
    Args:
        menu_id: The unique identifier for the menu item
        permission_update: Object containing list of group IDs that should have access
    
    Returns:
        Updated menu item with new permissions
    
    Example:
        PUT /api/menu-permissions/dashboard/permissions
        {
            "group_ids": [1, 2, 3]
        }
    
    Note:
        This replaces all existing permissions. To add/remove individual groups,
        fetch current permissions first, modify the list, then update.
    """
    updated_menu = crud_menu.update_menu_permissions(
        db, 
        menu_id, 
        permission_update.group_ids
    )
    
    if not updated_menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item '{menu_id}' not found"
        )
    
    return updated_menu


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(menu_id: str, db: Session = Depends(get_db)):
    """
    Delete a menu item.
    
    This will also remove all permission associations automatically
    due to CASCADE delete on the association table.
    
    Args:
        menu_id: The unique identifier for the menu item to delete
    
    Returns:
        No content (204 status code)
    
    Warning:
        This action cannot be undone. If this menu has children (nested menus),
        they will also be deleted due to CASCADE.
    """
    success = crud_menu.delete_menu_item(db, menu_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu item '{menu_id}' not found"
        )
    
    return None