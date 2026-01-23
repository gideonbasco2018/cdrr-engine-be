# app/api/routers/analytics.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.session import get_db
from app.schemas.analytics import (
    ReceivedAnalyticsResponse,
    ReceivedByPeriodResponse,
    MonthlyBreakdown,
)
from app.crud import analytics as crud_analytics

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"]
)
<<<<<<< HEAD
=======

>>>>>>> 6eb3909 (Update backend in production)

@router.get(
    "/received",
    response_model=ReceivedAnalyticsResponse,
    summary="Count received applications (FDAC vs Central)",
)
def received_applications_analytics(
    year: int = Query(..., ge=2000, description="Year (YYYY)"),
    month: Optional[int] = Query(None, ge=1, le=12),
    day: Optional[int] = Query(None, ge=1, le=31),
    db: Session = Depends(get_db),
):
    """
    Analytics endpoint to count received applications based on:
    - DB_DATE_RECEIVED_FDAC
    - DB_DATE_RECEIVED_CENT

    Filters: year (required), month/day (optional)
    """

    fdac_count = crud_analytics.count_received_fdac(
        db=db, year=year, month=month, day=day
    )

    central_count = crud_analytics.count_received_central(
        db=db, year=year, month=month, day=day
    )

    return ReceivedAnalyticsResponse(
        year=year,
        month=month,
        day=day,
        fdac=fdac_count,
        central=central_count,
    )


@router.get(
    "/received-by-period",
    response_model=ReceivedByPeriodResponse,
    summary="Get received applications breakdown by month or year",
)
def received_applications_by_period(
    year: Optional[int] = Query(None, ge=2000, description="Filter by specific year"),
    breakdown: str = Query("month", regex="^(month|year)$", description="Breakdown type: 'month' or 'year'"),
    db: Session = Depends(get_db),
):
    """
    Get received applications breakdown for bar graph visualization.
    
    - If breakdown='month' and year is provided: Returns monthly breakdown for that year (Jan-Dec)
    - If breakdown='month' and year is None: Returns monthly breakdown for current year
    - If breakdown='year': Returns yearly breakdown (last 5 years)
    
    Each period shows FDAC count, Central count, and total.
    """
    
    if breakdown == "month":
        # Get monthly breakdown
        data = crud_analytics.get_monthly_breakdown(db=db, year=year)
        return ReceivedByPeriodResponse(
            breakdown="month",
            year=year,
            data=data,
        )
    else:  # breakdown == "year"
        # Get yearly breakdown (last 5 years)
        data = crud_analytics.get_yearly_breakdown(db=db)
        return ReceivedByPeriodResponse(
            breakdown="year",
            year=None,
            data=data,
        )