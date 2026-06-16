# app/api/routes/frp_monitoring.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.frp_monitoring import (
    FRPKpiSummaryResponse,
    FRPStatusDistributionResponse,
    FRPDocTypesResponse,
    FRPTopCountriesResponse,
    FRPProductCategoriesResponse,
    FRPComplianceResponse,
    FRPCprTrendResponse,
    FRPRecentActivityResponse,
    FRPAlertsResponse,
    FRPApplicationsListResponse,
    FRPFilterOptionsResponse,
)
from app.crud import frp_monitoring as crud

router = APIRouter(
    prefix="/api/frp-monitoring",
    tags=["FRP Monitoring"],
)


@router.get("/kpi-summary", response_model=FRPKpiSummaryResponse)
def get_kpi_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_kpi_summary(db)


@router.get("/status-distribution", response_model=FRPStatusDistributionResponse)
def get_status_distribution(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_status_distribution(db)


@router.get("/doc-types", response_model=FRPDocTypesResponse)
def get_doc_types(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_doc_types(db)


@router.get("/top-countries", response_model=FRPTopCountriesResponse)
def get_top_countries(
    entity_type: str = Query(
        "manufacturer",
        description="manufacturer|trader|importer|distributor|repacker",
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_top_countries(db, entity_type=entity_type)


@router.get("/product-categories", response_model=FRPProductCategoriesResponse)
def get_product_categories(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_product_categories(db)


@router.get("/compliance", response_model=FRPComplianceResponse)
def get_compliance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_compliance(db)


@router.get("/cpr-trend", response_model=FRPCprTrendResponse)
def get_cpr_trend(
    year: Optional[int] = Query(None, description="Filter by year e.g. 2025"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_cpr_trend(db, year=year)


@router.get("/recent-activity", response_model=FRPRecentActivityResponse)
def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_recent_activity(db, limit=limit)


@router.get("/alerts", response_model=FRPAlertsResponse)
def get_alerts(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_alerts(db)


@router.get("/app-status-breakdown")
def get_app_status_breakdown(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_app_status_breakdown(db)


@router.get("/reviewer-workload")
def get_reviewer_workload(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_reviewer_workload(db)


@router.get("/filter-options", response_model=FRPFilterOptionsResponse)
def get_filter_options(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return distinct dropdown values for the advanced filter panel."""
    return crud.get_filter_options(db)


@router.get("/field-suggestions")
def get_field_suggestions(
    field: str = Query(..., description="lto_company|brand_name|generic_name|dosage_form|uploaded_by|manufacturer|trader|importer|distributor|repacker"),
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return up to 10 autocomplete suggestions for a text filter field."""
    return {"suggestions": crud.get_field_suggestions(db, field=field, q=q)}


@router.get("/applications", response_model=FRPApplicationsListResponse)
def get_applications_list(
    # ── quick presets ──────────────────────────────────────────────────────
    filter_type: Optional[str] = Query(
        None, description="all|released_this_month|pending_compliance|overdue"
    ),
    search:    Optional[str] = Query(None),
    period:    Optional[str] = Query(None, description="YYYY-MM — filter by received or released month"),
    period_type: Optional[str] = Query(None, description="received | released | both (default)"),
    page:      int = Query(1,   ge=1),
    page_size: int = Query(100, ge=1, le=500),
    # ── general advanced ──────────────────────────────────────────────────
    est_cat:            Optional[str] = Query(None),
    app_type:           Optional[str] = Query(None),
    lto_company:        Optional[str] = Query(None),
    brand_name:         Optional[str] = Query(None),
    generic_name:       Optional[str] = Query(None),
    dosage_form:        Optional[str] = Query(None),
    doc_type:           Optional[str] = Query(None),
    uploaded_by:        Optional[str] = Query(None),
    upload_date_from:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    upload_date_to:     Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_received_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_received_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_released_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_released_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
    # ── supply chain advanced ─────────────────────────────────────────────
    manufacturer:         Optional[str] = Query(None),
    manufacturer_country: Optional[str] = Query(None),
    trader:               Optional[str] = Query(None),
    trader_country:       Optional[str] = Query(None),
    importer:             Optional[str] = Query(None),
    importer_country:     Optional[str] = Query(None),
    distributor:          Optional[str] = Query(None),
    distributor_country:  Optional[str] = Query(None),
    repacker:             Optional[str] = Query(None),
    repacker_country:     Optional[str] = Query(None),
    # ── auth / db ─────────────────────────────────────────────────────────
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return crud.get_applications_list(
        db,
        filter_type=filter_type,
        search=search,
        period=period,
        period_type=period_type,
        page=page,
        page_size=page_size,
        est_cat=est_cat,
        app_type=app_type,
        lto_company=lto_company,
        brand_name=brand_name,
        generic_name=generic_name,
        dosage_form=dosage_form,
        doc_type=doc_type,
        uploaded_by=uploaded_by,
        upload_date_from=upload_date_from,
        upload_date_to=upload_date_to,
        date_received_from=date_received_from,
        date_received_to=date_received_to,
        date_released_from=date_released_from,
        date_released_to=date_released_to,
        manufacturer=manufacturer,
        manufacturer_country=manufacturer_country,
        trader=trader,
        trader_country=trader_country,
        importer=importer,
        importer_country=importer_country,
        distributor=distributor,
        distributor_country=distributor_country,
        repacker=repacker,
        repacker_country=repacker_country,
    )
