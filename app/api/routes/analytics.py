
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
    AnalyticsFRPTATResponse,
    AnalyticsFRPTATOutlierResponse
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


@router.get("/frp-tat-trend", response_model=AnalyticsFRPTATResponse)
def get_frp_tat_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    db: Session = Depends(get_db),
):
    """
    Returns the TAT trend for FRP and CRP applications grouped by quarter.
    
    Filters:
    - year: e.g. "2025", "2026", or "All"
    - month: e.g. "1" to "12", or "All"
    """
    data = crud_analytics.get_analytics_frp_tat_trend(db, year=year, month=month)
    return {"data": data}

@router.get("/frp-tat-outliers", response_model=AnalyticsFRPTATOutlierResponse)
def get_frp_tat_outliers(
    extreme_threshold: int = Query(365, ge=1),
    db: Session = Depends(get_db),
):
    """
    Returns suspicious FRP & CRP records:
    - negative_tat: released before received (data entry error)
    - extreme_tat:  TAT exceeds threshold in days (default 365)

    Adjust extreme_threshold query param as needed.
    e.g. /frp-tat-outliers?extreme_threshold=180
    """
    return crud_analytics.get_analytics_frp_tat_outliers(
        db, extreme_threshold=extreme_threshold
    )