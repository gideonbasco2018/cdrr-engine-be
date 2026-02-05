# ============================================================
# FILE: app/schemas/menu_permissions.py
# ============================================================

from pydantic import BaseModel, Field
from typing import List, Optional


class GroupBase(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True


class MenuItemBase(BaseModel):
    menu_id: str
    name: str
    path: str
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order: int = 0


class MenuItemCreate(MenuItemBase):
    """Schema for creating a new menu item"""
    pass


class MenuItemUpdate(BaseModel):
    """Schema for updating menu item details (not permissions)"""
    name: Optional[str] = None
    path: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order: Optional[int] = None


class MenuPermissionResponse(BaseModel):
    """Schema for menu item with group permissions"""
    id: int
    menu_id: str
    name: str
    path: str
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order: int
    group_ids: List[int]
    groups: List[GroupBase] = []
    
    class Config:
        from_attributes = True


class MenuPermissionUpdate(BaseModel):
    """Schema for updating menu item permissions"""
    group_ids: List[int] = Field(..., description="List of group IDs that can access this menu item")


class MenuItemListResponse(BaseModel):
    """Simplified response for listing menus (without permissions)"""
    id: int
    menu_id: str
    name: str
    path: str
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    order: int
    
    class Config:
        from_attributes = True