# app/api/routes/fda_verification_statistics.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, date, timedelta

from app.core.deps import get_current_active_user
from app.crud import fda_verification_statistics as crud

router = APIRouter(
    prefix="/api/fda/stats",
    tags=["FDA Verification Statistics"],
    dependencies=[Depends(get_current_active_user)]
)


@router.get("/dashboard")
async def get_dashboard_statistics(
    uploaded_by: Optional[str] = Query(None, description="Filter by uploader username")
):
    """
    Get dashboard statistics for FDA Verification Portal
    
    Returns:
    - Total Manual Application Released
    - Active Products (not expired, not canceled)
    - Expired products
    - My Uploads Today
    - My Uploads Yesterday
    - My Uploads This Month
    - Duplicate Records
    - Cancelled records
    """
    try:
        stats = crud.get_dashboard_statistics(uploaded_by=uploaded_by)
        
        return {
            "status": "success",
            "data": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/upload-history")
async def get_upload_history(
    uploaded_by: Optional[str] = Query(None, description="Filter by uploader username"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back")
):
    """
    Get upload history (daily breakdown)
    """
    try:
        history = crud.get_upload_history(
            uploaded_by=uploaded_by,
            days=days
        )
        
        return {
            "status": "success",
            "data": history
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve upload history: {str(e)}"
        )

@router.get("/expiry-analysis")
async def get_expiry_analysis(
    uploaded_by: Optional[str] = Query(None, description="Filter by uploader username")
):
    """
    Get expiry analysis
    - Expiring Soon (within 30 days)
    - Expiring This Month
    - Expiring This Year
    - Already Expired
    """
    try:
        analysis = crud.get_expiry_analysis(uploaded_by=uploaded_by)
        
        return {
            "status": "success",
            "data": analysis
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve expiry analysis: {str(e)}"
        )