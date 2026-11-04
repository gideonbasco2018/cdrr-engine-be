# app/api/routes/analytics.py

from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.crud import company_monitoring as crud_company_monitoring
from app.crud import evaluator_monitoring as crud_evaluator_monitoring
from app.crud import generic_monitoring as crud_generic_monitoring

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_active_user)],
)


def require_evaluator_monitoring_access(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """User Insights is open only to the groups listed in the crud file."""
    group_ids = {g.id for g in current_user.groups}
    if not group_ids & crud_evaluator_monitoring.ALLOWED_GROUP_IDS:
        raise HTTPException(status_code=403, detail="Not allowed to view User Insights")
    return current_user


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


@router.get("/trend/received-released")
def get_trend_received_released(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_received_released_trend(
        db, year=year, month=month, prescription=prescription
    )


@router.get("/trend/records")
def get_trend_records(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    kind: str = Query(
        "received",
        description="received|released|received_released|received_in_progress|received_other",
    ),
    bucket: int = Query(None, description="clicked year (year=All) or month"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None, description="Normalized DB_APP_STATUS, or __NONE__"),
    doc_type: str = Query(None, description="Normalized doc type, or __NONE__"),
    classification: str = Query(None, description="Product class, or __NONE__"),
    received_from: date = Query(None),
    received_to: date = Query(None),
    released_from: date = Query(None),
    released_to: date = Query(None),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_trend_records(
        db,
        year=year,
        month=month,
        prescription=prescription,
        kind=kind,
        bucket=bucket,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        doc_type=doc_type,
        classification=classification,
        received_from=received_from,
        received_to=received_to,
        released_from=released_from,
        released_to=released_to,
    )


@router.get("/trend/timeline")
def get_trend_timeline(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    kind: str = Query(
        "received",
        description="received|released|received_released|received_in_progress|received_other",
    ),
    bucket: int = Query(None, description="clicked year (year=All) or month"),
    group_by: str = Query("year", description="year|month|day"),
    bucket_year: int = Query(None, ge=2000, le=2100),
    bucket_month: int = Query(None, ge=1, le=12),
    basis: str = Query(None, description="received|released"),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None),
    doc_type: str = Query(None),
    classification: str = Query(None, description="Product class, or __NONE__"),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_trend_timeline(
        db,
        year=year,
        month=month,
        prescription=prescription,
        kind=kind,
        bucket=bucket,
        group_by=group_by,
        bucket_year=bucket_year,
        bucket_month=bucket_month,
        basis=basis,
        search=search,
        status=status,
        doc_type=doc_type,
        classification=classification,
    )


@router.get("/by-classification", response_model=AnalyticsClassificationResponse)
def get_by_classification(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    status: str = Query("all", description="all|completed|in_progress"),
    db: Session = Depends(get_db),
):
    data, doc_types = crud_analytics.get_analytics_by_classification(
        db, year=year, month=month, prescription=prescription, status=status
    )
    return {"data": data, "doc_types": doc_types}


@router.get("/by-classification/records")
def get_by_classification_records(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    classification: str = Query(None, description="Class name; empty = all classes"),
    tab: str = Query("completed", description="completed|in_progress"),
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
    return crud_analytics.get_analytics_classification_records(
        db,
        year=year,
        month=month,
        prescription=prescription,
        classification=classification,
        tab=tab,
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


@router.get("/by-classification/trend")
def get_by_classification_trend(
    year: str = Query("All"),
    month: str = Query("All"),
    prescription: str = Query("All"),
    classification: str = Query(None, description="Class name; empty = all classes"),
    tab: str = Query("completed", description="completed|in_progress"),
    group_by: str = Query("year", description="year|month"),
    bucket_year: int = Query(None, ge=2000, le=2100, description="needed for month"),
    basis: str = Query("received", description="received|released"),
    search: str = Query(None, description="Filter by DTN"),
    status: str = Query(None),
    doc_type: str = Query(None),
    db: Session = Depends(get_db),
):
    return crud_analytics.get_analytics_classification_trend(
        db,
        year=year,
        month=month,
        prescription=prescription,
        classification=classification,
        tab=tab,
        group_by=group_by,
        bucket_year=bucket_year,
        basis=basis,
        search=search,
        status=status,
        doc_type=doc_type,
    )


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
    kind: str = Query("released", description="received|in_progress|released"),
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


@router.get("/company-monitoring/search")
def search_company_names(
    q: str = Query(..., min_length=2, description="Part of the company name"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return {"data": crud_company_monitoring.search_companies(db, q, limit)}


@router.get("/company-monitoring")
def get_company_monitoring_route(
    company: List[str] = Query(..., description="One or more company names"),
    year: str = Query("All"),
    month: str = Query("All", description="All or 1-12 (needs a year)"),
    basis: str = Query("received", description="received|released"),
    db: Session = Depends(get_db),
):
    return crud_company_monitoring.get_company_monitoring(
        db, companies=company, year=year, month=month, basis=basis
    )


@router.get("/company-monitoring/records")
def get_company_monitoring_records_route(
    company: List[str] = Query(..., description="One or more company names"),
    year: str = Query("All"),
    month: str = Query("All"),
    basis: str = Query("received", description="received|released"),
    user_id: str = Query(None, description="evaluator id, 'none' = Unassigned"),
    search: str = Query(None, description="DTN or drug name"),
    sort: str = Query("received", description="received|tat"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud_company_monitoring.get_company_records(
        db,
        companies=company,
        year=year,
        month=month,
        basis=basis,
        user_id=user_id,
        search=search,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/company-monitoring/released-docs")
def get_company_released_docs_route(
    company: List[str] = Query(..., description="One or more company names"),
    year: str = Query("All"),
    month: str = Query("All"),
    view: str = Query("released", description="received|released"),
    db: Session = Depends(get_db),
):
    return crud_company_monitoring.get_company_released_docs(
        db, companies=company, year=year, month=month, view=view
    )


@router.get("/company-monitoring/released-docs/records")
def get_company_released_doc_records_route(
    company: List[str] = Query(..., description="One or more company names"),
    doc: str = Query(..., description="Document type, or 'No document type'"),
    year: str = Query("All"),
    month: str = Query("All"),
    view: str = Query("released", description="received|released"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud_company_monitoring.get_company_released_doc_records(
        db,
        companies=company,
        doc=doc,
        year=year,
        month=month,
        view=view,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/evaluator-monitoring/search",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def search_evaluator_names(
    q: str = Query("", description="Part of the name or code; empty lists everyone"),
    limit: int = Query(15, ge=1, le=500),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    sources: str = Query("cpr", description="cpr, fgmp or cpr,fgmp"),
    db: Session = Depends(get_db),
):
    return {
        "data": crud_evaluator_monitoring.search_evaluators(
            db, q, limit, role, sources
        )
    }


@router.get(
    "/evaluator-monitoring/years",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def get_evaluator_monitoring_years_route(
    user_id: int = Query(..., description="Evaluator's user id"),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    sources: str = Query("cpr", description="cpr, fgmp or cpr,fgmp"),
    db: Session = Depends(get_db),
):
    return {
        "years": crud_evaluator_monitoring.get_evaluator_years(
            db, user_id=user_id, role=role, sources=sources
        )
    }


@router.get(
    "/evaluator-monitoring",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def get_evaluator_monitoring_route(
    user_id: int = Query(..., description="Evaluator's user id"),
    year: str = Query("All"),
    month: str = Query("All", description="All or 1-12 (needs a year)"),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    source: str = Query(None, description="TAT source filter, e.g. decked:released"),
    split: str = Query(
        "year", description="year|month: how the Received/Released splits are cut"
    ),
    db: Session = Depends(get_db),
):
    data = crud_evaluator_monitoring.get_evaluator_monitoring(
        db,
        user_id=user_id,
        year=year,
        month=month,
        role=role,
        source=source,
        split=split,
        sources=sources,
    )
    if data is None:
        raise HTTPException(status_code=404, detail="Evaluator not found")
    return data


@router.get(
    "/evaluator-monitoring/records",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def get_evaluator_monitoring_records_route(
    user_id: int = Query(..., description="Evaluator's user id"),
    kind: str = Query(..., description="company|drug"),
    key: str = Query(
        ..., description="The row's key, as sent by /evaluator-monitoring"
    ),
    year: str = Query("All"),
    month: str = Query("All", description="All or 1-12 (needs a year)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=2000),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    source: str = Query(None, description="TAT source filter, e.g. decked:released"),
    sources: str = Query("cpr", description="cpr, fgmp or cpr,fgmp"),
    db: Session = Depends(get_db),
):
    return crud_evaluator_monitoring.get_evaluator_records(
        db,
        user_id=user_id,
        kind=kind,
        key=key,
        year=year,
        month=month,
        page=page,
        page_size=page_size,
        role=role,
        source=source,
        sources=sources,
    )


@router.get(
    "/evaluator-monitoring/period-records",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def get_evaluator_monitoring_period_records_route(
    user_id: int = Query(..., description="Evaluator's user id"),
    side: str = Query(..., description="received|released|either"),
    bucket: int = Query(
        ..., description="the year, or the month when a year is chosen"
    ),
    year: str = Query("All"),
    month: str = Query("All"),
    other_year: int = Query(None, description="released in / received in this year"),
    other_month: int = Query(None, description="...and in this month (1-12)"),
    company_key: str = Query(None, description="only this company (its key)"),
    drug_key: str = Query(None, description="only this drug (its key)"),
    doc_type: str = Query(None, description="only this document type"),
    rest: bool = Query(False, description="not released yet / no received date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=2000),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    sources: str = Query("cpr", description="cpr, fgmp or cpr,fgmp"),
    db: Session = Depends(get_db),
):
    return crud_evaluator_monitoring.get_period_records(
        db,
        user_id=user_id,
        side=side,
        bucket=bucket,
        year=year,
        month=month,
        other_year=other_year,
        other_month=other_month,
        company_key=company_key,
        drug_key=drug_key,
        doc_type=doc_type,
        rest=rest,
        page=page,
        page_size=page_size,
        role=role,
        sources=sources,
    )


@router.get("/company-monitoring/kpi-records")
def get_company_kpi_records_route(
    company: List[str] = Query(..., description="One or more company names"),
    kind: str = Query(..., description="received|processed|open|tat|within|beyond"),
    year: str = Query("All"),
    month: str = Query("All"),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=200),
    search: str = Query(None, description="DTN or drug name"),
    state: str = Query(None, description="released|open"),
    doc: str = Query(None, description="Document type released"),
    result: str = Query(None, description="within|beyond|none"),
    db: Session = Depends(get_db),
):
    return crud_company_monitoring.get_company_kpi_records(
        db,
        companies=company,
        kind=kind,
        year=year,
        month=month,
        page=page,
        page_size=page_size,
        search=search,
        state=state,
        doc=doc,
        result=result,
    )


@router.get("/generic-monitoring/search")
def search_generic_names(
    q: str = Query(..., min_length=2, description="Part of the generic name"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return {"data": crud_generic_monitoring.search_generics(db, q, limit)}


@router.get("/generic-monitoring")
def get_generic_monitoring_route(
    generic: List[str] = Query(..., description="One or more generic names"),
    db: Session = Depends(get_db),
):
    return crud_generic_monitoring.get_generic_summary(db, generics=generic)


@router.get("/generic-monitoring/records")
def get_generic_monitoring_records_route(
    generic: List[str] = Query(..., description="One or more generic names"),
    group: str = Query("all", description="all|pending|registered|lod|other"),
    search: str = Query(None, description="DTN, brand, generic or company"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud_generic_monitoring.get_generic_records(
        db,
        generics=generic,
        group=group,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/evaluator-monitoring/month-summary",
    dependencies=[Depends(require_evaluator_monitoring_access)],
)
def get_evaluator_monitoring_month_summary_route(
    user_id: int = Query(..., description="Evaluator's user id"),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    role: str = Query("evaluator", description="evaluator, checker or evaluator,checker"),
    sources: str = Query("cpr", description="cpr, fgmp or cpr,fgmp"),
    db: Session = Depends(get_db),
):
    return crud_evaluator_monitoring.get_month_summary(
        db, user_id=user_id, year=year, month=month, role=role, sources=sources
    )
