# app/api/routers/analytics.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.analytics import ReceivedAnalyticsResponse
from app.crud import analytics as crud_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])


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
