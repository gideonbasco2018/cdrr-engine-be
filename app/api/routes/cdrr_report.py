"""
CDRR Inspector Report Routes
CRUD operations for CDRR reports with FROO and Secondary nested data
Accessible by: CDRR, FROO/Inspector, FDAC groups + Admin/SuperAdmin
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User, UserRole
from app.crud import cdrr_report as crud
from app.schemas.cdrr_report import (
    CDRRReportCreate,
    CDRRReportUpdate,
    CDRRReportResponse,
    CDRRReportListResponse
)

router = APIRouter(
    prefix="/api/cdrr-reports",
    tags=["CDRR Inspector Reports"],
)


# ========================================
# HELPERS
# ========================================

def check_cdrr_access(current_user: User):
    """
    Allow access to users in specific groups OR admins
    Allowed groups: CDRR (14), Inspector/FROO (10), FDAC (13)
    """
    # Allow admins/superadmins
    if current_user.role in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        return True
    
    # Check if user is in allowed groups
    if hasattr(current_user, 'groups') and current_user.groups:
        allowed_group_ids = [10, 13, 14]  # Inspector/FROO, FDAC, CDRR
        allowed_group_names = ['Inspector', 'FROO', 'FDAC', 'CDRR']
        
        user_group_ids = [g.id for g in current_user.groups]
        user_group_names = [g.name for g in current_user.groups]
        
        # Check by ID or name
        has_access = (
            any(gid in user_group_ids for gid in allowed_group_ids) or
            any(gname in user_group_names for gname in allowed_group_names)
        )
        
        if has_access:
            return True
    
    # No access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Required: CDRR, FROO, Inspector, or FDAC group membership.",
    )


def check_cdrr_write_permission(current_user: User):
    """
    Check if user can CREATE/UPDATE/DELETE reports
    Allowed: CDRR (14), Inspector/FROO (10), Admin, SuperAdmin
    """
    # Allow admins/superadmins
    if current_user.role in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        return True
    
    # Check if user is in write-enabled groups
    if hasattr(current_user, 'groups') and current_user.groups:
        write_group_ids = [10, 14]  # Inspector/FROO, CDRR
        write_group_names = ['Inspector', 'FROO', 'CDRR']
        
        user_group_ids = [g.id for g in current_user.groups]
        user_group_names = [g.name for g in current_user.groups]
        
        has_write = (
            any(gid in user_group_ids for gid in write_group_ids) or
            any(gname in user_group_names for gname in write_group_names)
        )
        
        if has_write:
            return True
    
    # No write access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Required: CDRR, FROO, or Inspector group membership for write operations.",
    )


# ========================================
# CDRR REPORT CRUD
# ========================================

@router.post("", response_model=CDRRReportResponse, status_code=status.HTTP_201_CREATED)
def create_cdrr_report(
    report: CDRRReportCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create a new CDRR report with optional FROO and Secondary data
    
    **Permissions:** CDRR, FROO, Inspector groups, Admin, SuperAdmin
    """
    check_cdrr_write_permission(current_user)
    return crud.create_cdrr_report(db, report, current_user.id)


@router.get("", response_model=CDRRReportListResponse)
def get_cdrr_reports(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by DTN, importer, LTO, manufacturer, or certificate"),
    status: Optional[str] = Query(None, description="Filter by status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get paginated list of CDRR reports with filtering and search
    
    **Permissions:** CDRR, FROO, Inspector, FDAC groups, Admin, SuperAdmin
    """
    check_cdrr_access(current_user)
    
    skip = (page - 1) * page_size
    
    reports, total = crud.get_cdrr_reports(
        db,
        skip=skip,
        limit=page_size,
        search=search,
        status=status,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return CDRRReportListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=reports
    )


@router.get("/{report_id}", response_model=CDRRReportResponse)
def get_cdrr_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific CDRR report by ID with nested data
    
    **Permissions:** CDRR, FROO, Inspector, FDAC groups, Admin, SuperAdmin
    """
    check_cdrr_access(current_user)
    
    report = crud.get_cdrr_report(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CDRR report {report_id} not found"
        )
    
    return report


@router.put("/{report_id}", response_model=CDRRReportResponse)
def update_cdrr_report(
    report_id: int,
    report_update: CDRRReportUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update a CDRR report and its nested data
    
    **Permissions:** CDRR, FROO, Inspector groups, Admin, SuperAdmin
    """
    check_cdrr_write_permission(current_user)
    
    updated_report = crud.update_cdrr_report(
        db, report_id, report_update, current_user.id
    )
    
    if not updated_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CDRR report {report_id} not found"
        )
    
    return updated_report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cdrr_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Delete (soft delete) a CDRR report and its nested data
    
    **Permissions:** CDRR, FROO, Inspector groups, Admin, SuperAdmin
    """
    check_cdrr_write_permission(current_user)
    
    success = crud.delete_cdrr_report(db, report_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CDRR report {report_id} not found"
        )


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_cdrr_reports(
    report_ids: list[int],
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Bulk delete (soft delete) multiple CDRR reports and their nested data
    
    **Permissions:** CDRR, FROO, Inspector groups, Admin, SuperAdmin
    """
    check_cdrr_write_permission(current_user)
    
    deleted_count = crud.bulk_delete_cdrr_reports(db, report_ids, current_user.id)
    
    return {
        "success": True,
        "message": f"Successfully deleted {deleted_count} reports",
        "deleted_count": deleted_count
    }