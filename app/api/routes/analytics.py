# # app/api/routers/analytics.py
# from fastapi import APIRouter, Depends, Query
# from sqlalchemy.orm import Session
# from typing import Optional, List

# from app.db.session import get_db
# from app.schemas.analytics import (
#     ReceivedAnalyticsResponse,
#     ReceivedByPeriodResponse,
#     MonthlyBreakdown,
# )
# from app.crud import analytics as crud_analytics

# router = APIRouter(
#     prefix="/api/analytics",
#     tags=["Analytics"]
# )

# @router.get(
#     "/received",
#     response_model=ReceivedAnalyticsResponse,
#     summary="Count received applications (FDAC vs Central)",
# )
# def received_applications_analytics(
#     year: int = Query(..., ge=2000, description="Year (YYYY)"),
#     month: Optional[int] = Query(None, ge=1, le=12),
#     day: Optional[int] = Query(None, ge=1, le=31),
#     db: Session = Depends(get_db),
# ):
#     """
#     Analytics endpoint to count received applications based on:
#     - DB_DATE_RECEIVED_FDAC
#     - DB_DATE_RECEIVED_CENT

#     Filters: year (required), month/day (optional)
#     """

#     fdac_count = crud_analytics.count_received_fdac(
#         db=db, year=year, month=month, day=day
#     )

#     central_count = crud_analytics.count_received_central(
#         db=db, year=year, month=month, day=day
#     )

#     return ReceivedAnalyticsResponse(
#         year=year,
#         month=month,
#         day=day,
#         fdac=fdac_count,
#         central=central_count,
#     )


# @router.get(
#     "/received-by-period",
#     response_model=ReceivedByPeriodResponse,
#     summary="Get received applications breakdown by month or year",
# )
# def received_applications_by_period(
#     year: Optional[int] = Query(None, ge=2000, description="Filter by specific year"),
#     breakdown: str = Query("month", regex="^(month|year)$", description="Breakdown type: 'month' or 'year'"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Get received applications breakdown for bar graph visualization.
    
#     - If breakdown='month' and year is provided: Returns monthly breakdown for that year (Jan-Dec)
#     - If breakdown='month' and year is None: Returns monthly breakdown for current year
#     - If breakdown='year': Returns yearly breakdown (last 5 years)
    
#     Each period shows FDAC count, Central count, and total.
#     """
    
#     if breakdown == "month":
#         # Get monthly breakdown
#         data = crud_analytics.get_monthly_breakdown(db=db, year=year)
#         return ReceivedByPeriodResponse(
#             breakdown="month",
#             year=year,
#             data=data,
#         )
#     else:  # breakdown == "year"
#         # Get yearly breakdown (last 5 years)
#         data = crud_analytics.get_yearly_breakdown(db=db)
#         return ReceivedByPeriodResponse(
#             breakdown="year",
#             year=None,
#             data=data,
#         )

# NEW/ 5-15

# app/api/routes/analytics.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    AnalyticsTrendResponse,
    AnalyticsClassificationResponse,
    AnalyticsYearSummaryResponse,
    AnalyticsTopDrugsResponse,
    AnalyticsTopCountriesResponse,
    AnalyticsAvailableYearsResponse,
)
from app.crud import analytics as crud_analytics

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/available-years", response_model=AnalyticsAvailableYearsResponse)
def get_available_years(db: Session = Depends(get_db)):
    years = crud_analytics.get_analytics_available_years(db)
    return {"years": years}


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_summary(db, year=year, month=month, prescription=prescription)


@router.get("/trend", response_model=AnalyticsTrendResponse)
def get_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_trend(db, year=year, month=month, prescription=prescription)
    return {"data": data}


@router.get("/by-classification", response_model=AnalyticsClassificationResponse)
def get_by_classification(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_by_classification(db, year=year, month=month, prescription=prescription)
    return {"data": data}


@router.get("/year-summary", response_model=AnalyticsYearSummaryResponse)
def get_year_summary(db: Session = Depends(get_db)):
    data = crud_analytics.get_analytics_year_summary(db)
    return {"data": data}


@router.get("/top-drugs", response_model=AnalyticsTopDrugsResponse)
def get_top_drugs(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_top_drugs(db, year=year, month=month, prescription=prescription, limit=limit)
    return {"data": data}


@router.get("/top-countries", response_model=AnalyticsTopCountriesResponse)
def get_top_countries(
    entity_type: str = Query("mfr"),
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_top_countries(
        db, entity_type=entity_type, year=year,
        month=month, prescription=prescription, limit=limit,
    )
    return {"data": data}