# app/api/routes/analytics.py

from datetime import date
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
    AnalyticsFRPTATOutlierResponse,
    CountryYearTrendResponse,
)
from app.crud import analytics as crud_analytics
from app.crud import top_companies as crud_top_companies
from app.crud import fastest_processing as crud_fastest

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
    return crud_analytics.get_analytics_summary(
        db, year=year, month=month, prescription=prescription
    )


@router.get("/summary/records")
def get_summary_records(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    doc: str = Query("cpr", description="cpr|lod"),
    expiry: str = Query("all", description="all|expired|not_expired|none"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None, description="Normalized DB_APP_STATUS, or __NONE__"),
    doc_type: str = Query(None, description="Normalized doc type, or __NONE__"),
    completed_only: bool = Query(False, description="Only COMPLETED applications"),
    received_from: date = Query(None),
    received_to: date = Query(None),
    released_from: date = Query(None),
    released_to: date = Query(None),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_summary_records(
        db,
        year=year,
        month=month,
        prescription=prescription,
        doc=doc,
        expiry=expiry,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
        completed_only=completed_only,
        received_from=received_from,
        received_to=received_to,
        released_from=released_from,
        released_to=released_to,
    )


@router.get("/trend", response_model=AnalyticsTrendResponse)
def get_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_trend(
        db, year=year, month=month, prescription=prescription
    )
    return {"data": data}


@router.get("/by-classification", response_model=AnalyticsClassificationResponse)
def get_by_classification(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    data, doc_types = crud_analytics.get_analytics_by_classification(
        db, year=year, month=month, prescription=prescription
    )
    return {"data": data, "doc_types": doc_types}


@router.get("/year-summary", response_model=AnalyticsYearSummaryResponse)
def get_year_summary(
    basis: str = Query("released", description="released|received"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_year_summary(db, basis=basis)
    return {"data": data}


@router.get("/year-summary/records")
def get_year_summary_records(
    year: str = Query(..., description="Year (2000-2100) or 'nodate'"),
    kind: str = Query("released", description="received|released"),
    basis: str = Query("released", description="released|received"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None, description="Normalized DB_APP_STATUS, or __NONE__"),
    doc_type: str = Query(None, description="Normalized doc type, or __NONE__"),
    received_from: date = Query(None),
    received_to: date = Query(None),
    released_from: date = Query(None),
    released_to: date = Query(None),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_year_records(
        db,
        year=year,
        kind=kind,
        basis=basis,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
        received_from=received_from,
        received_to=received_to,
        released_from=released_from,
        released_to=released_to,
    )


@router.get("/data-quality")
def get_data_quality(db: Session = Depends(get_db)):
    return {"data": crud_analytics.get_analytics_data_quality(db)}


@router.get("/data-quality/records")
def get_data_quality_records(
    year: str = Query("all", description="all | nodate | 2024 ..."),
    issue: str = Query(
        "incomplete",
        description="incomplete|missing_received|missing_released|complete",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None),
    doc_type: str = Query(None),
    received_from: date = Query(None),
    received_to: date = Query(None),
    released_from: date = Query(None),
    released_to: date = Query(None),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_quality_records(
        db,
        year=year,
        issue=issue,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
        received_from=received_from,
        received_to=received_to,
        released_from=released_from,
        released_to=released_to,
    )


@router.get("/top-companies")
def get_top_companies(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query("All", description="All or 1-12"),
    top: int = Query(10, ge=1, le=100),
    prescription: str = Query("All"),
    basis: str = Query("received", description="received|released"),
    db: Session = Depends(get_db),
):
    return crud_top_companies.get_top_companies(
        db,
        year=year,
        month=month,
        top=top,
        prescription=prescription,
        basis=basis,
    )


@router.get("/top-companies/records")
def get_top_company_records(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query("All"),
    prescription: str = Query("All"),
    basis: str = Query("received"),
    company: str = Query(...),
    user_id: str = Query(None, description="evaluator id, 'none' = Unassigned"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    status: str = Query(None),
    doc_type: str = Query(None),
    db: Session = Depends(get_db),
):
    return crud_top_companies.get_company_records(
        db,
        year=year,
        month=month,
        prescription=prescription,
        basis=basis,
        company=company,
        user_id=user_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
    )


@router.get("/fastest/applications")
def get_fastest_applications_route(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query("All", description="All or 1-12"),
    top: int = Query(10, ge=1, le=100),
    doc: str = Query("cpr", description="cpr|cert|both"),
    entry_type: str = Query(None, description="DB_ENTRY_TYPE, or __REGULAR__"),
    app_type: str = Query(
        None, description="Pipe-separated DB_APP_TYPE values; __NONE__ = blank"
    ),
    db: Session = Depends(get_db),
):
    return crud_fastest.get_fastest_applications(
        db,
        year=year,
        month=month,
        top=top,
        doc=doc,
        entry_type=entry_type,
        app_type=app_type,
    )


@router.get("/fastest/companies")
def get_fastest_companies_route(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query("All", description="All or 1-12"),
    top: int = Query(10, ge=1, le=100),
    min_apps: int = Query(3, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return crud_fastest.get_fastest_companies(
        db, year=year, month=month, top=top, min_apps=min_apps
    )


@router.get("/fastest/records")
def get_fastest_records_route(
    year: int = Query(..., ge=2000, le=2100),
    month: str = Query("All"),
    doc: str = Query("both", description="cpr|cert|both"),
    company: str = Query(None),
    user_id: str = Query(None, description="evaluator id, 'none' = Unassigned"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    status: str = Query(None),
    doc_type: str = Query(None),
    received_from: str = Query(None),
    received_to: str = Query(None),
    released_from: str = Query(None),
    released_to: str = Query(None),
    entry_type: str = Query(None),
    app_type: str = Query(None),
    db: Session = Depends(get_db),
):
    return crud_fastest.get_fastest_records(
        db,
        year=year,
        month=month,
        doc=doc,
        company=company,
        user_id=user_id,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
        received_from=received_from,
        received_to=received_to,
        released_from=released_from,
        released_to=released_to,
        entry_type=entry_type,
        app_type=app_type,
    )


@router.get("/top-drugs", response_model=AnalyticsTopDrugsResponse)
def get_top_drugs(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    limit: int = Query(8, ge=1),  # no upper cap
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_top_drugs(
        db, year=year, month=month, prescription=prescription, limit=limit
    )
    return {"data": data}


@router.get("/top-countries", response_model=AnalyticsTopCountriesResponse)
def get_top_countries(
    entity_type: str = Query("mfr"),
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    limit: int = Query(10, ge=1),  # no upper cap
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_top_countries(
        db,
        entity_type=entity_type,
        year=year,
        month=month,
        prescription=prescription,
        limit=limit,
    )
    return {"data": data}


@router.get("/frp-tat-trend", response_model=AnalyticsFRPTATResponse)
def get_frp_tat_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_analytics_frp_tat_trend(db, year=year, month=month)
    return {"data": data}


@router.get("/frp-tat-outliers", response_model=AnalyticsFRPTATOutlierResponse)
def get_frp_tat_outliers(
    extreme_threshold: int = Query(365, ge=1),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_frp_tat_outliers(
        db, extreme_threshold=extreme_threshold
    )


@router.get("/country-year-trend", response_model=CountryYearTrendResponse)
def get_country_year_trend(
    country: str = Query(..., description="Country name"),
    entity_type: str = Query(
        "mfr", description="mfr|trader|importer|distributor|repacker"
    ),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    data = crud_analytics.get_country_year_trend(
        db, country=country, entity_type=entity_type, prescription=prescription
    )
    return {"country": country, "entity_type": entity_type, "data": data}
