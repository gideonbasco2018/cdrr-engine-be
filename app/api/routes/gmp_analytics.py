# app/api/routes/gmp_analytics.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.schemas.gmp_analytics import (
    GMPAnalyticsAvailableYearsResponse,
    GMPAnalyticsSummaryResponse,
    GMPAnalyticsDTNSummaryResponse,
    GMPAnalyticsTrendResponse,
    GMPAnalyticsCategoryResponse,
    GMPAnalyticsStepTimingResponse,
    GMPAnalyticsWorkloadResponse,
    GMPAnalyticsAgingResponse,
    GMPAnalyticsNODResponse,
    GMPAnalyticsPicsCountryResponse,
)
from app.crud import gmp_analytics as crud_gmp_analytics

router = APIRouter(
    prefix="/api/gmp/analytics",
    tags=["GMP Analytics"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("/available-years", response_model=GMPAnalyticsAvailableYearsResponse)
def get_available_years(db: Session = Depends(get_db)):
    years = crud_gmp_analytics.get_gmp_analytics_available_years(db)
    return {"years": years}


@router.get("/summary", response_model=GMPAnalyticsSummaryResponse)
def get_summary(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    db: Session = Depends(get_db),
):
    return crud_gmp_analytics.get_gmp_analytics_summary(db, year=year, month=month, est_category=est_category)


@router.get("/dtn-summary", response_model=GMPAnalyticsDTNSummaryResponse)
def get_dtn_summary(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    db: Session = Depends(get_db),
):
    return crud_gmp_analytics.get_gmp_analytics_dtn_summary(db, year=year, month=month, est_category=est_category)


@router.get("/trend", response_model=GMPAnalyticsTrendResponse)
def get_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_gmp_analytics.get_gmp_analytics_trend(db, year=year, month=month, est_category=est_category)
    return {"data": data}


@router.get("/by-category", response_model=GMPAnalyticsCategoryResponse)
def get_by_category(
    year: str = Query("All"),
    month: str = Query("All"),
    limit: int = Query(10, ge=1),
    db: Session = Depends(get_db),
):
    return crud_gmp_analytics.get_gmp_analytics_by_category(db, year=year, month=month, limit=limit)


@router.get("/step-timing", response_model=GMPAnalyticsStepTimingResponse)
def get_step_timing(db: Session = Depends(get_db)):
    data = crud_gmp_analytics.get_gmp_analytics_step_timing(db)
    return {"data": data}


@router.get("/workload", response_model=GMPAnalyticsWorkloadResponse)
def get_workload(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    limit: int = Query(15, ge=1),
    db: Session = Depends(get_db),
):
    data = crud_gmp_analytics.get_gmp_analytics_workload(db, year=year, month=month, est_category=est_category, limit=limit)
    return {"data": data}


@router.get("/aging", response_model=GMPAnalyticsAgingResponse)
def get_aging(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_gmp_analytics.get_gmp_analytics_aging(db, year=year, month=month, est_category=est_category)
    return {"data": data}


@router.get("/nod", response_model=GMPAnalyticsNODResponse)
def get_nod(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    db: Session = Depends(get_db),
):
    return crud_gmp_analytics.get_gmp_analytics_nod(db, year=year, month=month, est_category=est_category)


@router.get("/pics-country", response_model=GMPAnalyticsPicsCountryResponse)
def get_pics_country(
    year: str = Query("All"),
    month: str = Query("All"),
    est_category: str = Query("All"),
    limit: int = Query(10, ge=1),
    mismatch_limit: int = Query(25, ge=1),
    db: Session = Depends(get_db),
):
    return crud_gmp_analytics.get_gmp_analytics_pics_country(
        db, year=year, month=month, est_category=est_category, limit=limit, mismatch_limit=mismatch_limit
    )
