# app/api/routes/dashboard.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Literal
from datetime import date
 
from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import dashboard as crud_dashboard
from app.crud import dashboard_chart as crud_chart
from app.schemas.dashboard import StatResponse, CombinedStatsResponse
from app.schemas.dashboard_chart import ChartResponse
from app.crud import dashboard_recent as crud_recent
from app.schemas.recent_applications import RecentApplicationsResponse

from app.crud import dashboard_detail as crud_detail
from app.schemas.dashboard_detail import MetricDetailResponse
from app.models.main_db import MainDB

router = APIRouter(
    prefix="/api/dashboard/stats",
    tags=["Dashboard Stats"],
)


# ─────────────────────────────────────────────────────────
# Impersonation helper
# ─────────────────────────────────────────────────────────
def _effective_username(
    current_user,
    impersonate: Optional[str],
) -> str:
    """
    Resolution order:
    1. ?impersonate=<username>  →  only honoured when current_user is admin
    2. current_user.username    →  default (own stats)
    """
    if impersonate and getattr(current_user, "is_admin", False):
        return impersonate
    return current_user.username


# ─────────────────────────────────────────────────────────
# Shared query params (reused across all 3 endpoints)
# ─────────────────────────────────────────────────────────
def _common_params(
    date_from:   Optional[date] = Query(None, description="Start date filter  YYYY-MM-DD"),
    date_to:     Optional[date] = Query(None, description="End date filter    YYYY-MM-DD"),
    impersonate: Optional[str]  = Query(None, description="Admin only: target username"),
):
    return {"date_from": date_from, "date_to": date_to, "impersonate": impersonate}


# ─────────────────────────────────────────────────────────
# 1. GET /dashboard/stats/received
# ─────────────────────────────────────────────────────────
@router.get(
    "/received",
    response_model=StatResponse,
    summary="Total applications received by the current user",
)
def get_received(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_received(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Total Received",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# 2. GET /dashboard/stats/completed
# ─────────────────────────────────────────────────────────
@router.get(
    "/completed",
    response_model=StatResponse,
    summary="Total completed applications for the current user",
)
def get_completed(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_completed(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="Completed",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# 3. GET /dashboard/stats/on-process
# ─────────────────────────────────────────────────────────
@router.get(
    "/on-process",
    response_model=StatResponse,
    summary="Total on-process applications for the current user",
)
def get_on_process(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    value    = crud_dashboard.get_total_on_process(
        db, username, params["date_from"], params["date_to"]
    )
    return StatResponse(
        label="On Process",
        value=value,
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
    )


# ─────────────────────────────────────────────────────────
# BONUS: GET /dashboard/stats/summary  (all 3 in one call)
# ─────────────────────────────────────────────────────────
@router.get(
    "/summary",
    response_model=CombinedStatsResponse,
    summary="All 3 KPI stats in one request",
)
def get_summary(
    params: dict = Depends(_common_params),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, params["impersonate"])
    stats    = crud_dashboard.get_stats_summary(
        db, username, params["date_from"], params["date_to"]
    )
    return CombinedStatsResponse(
        username=username,
        date_from=params["date_from"],
        date_to=params["date_to"],
        **stats,
    )


# ═════════════════════════════════════════════════════════
# CHART  (/api/dashboard/chart)
# ═════════════════════════════════════════════════════════
 
# ─────────────────────────────────────────────────────────
# GET /api/dashboard/chart
# ─────────────────────────────────────────────────────────
@router.get(
    "/chart",
    response_model=ChartResponse,
    summary="Time-series data for the Insights chart and data table",
    description="""
Returns aggregated **received / completed / on_process** counts
grouped by the requested breakdown:
 
| breakdown | label examples      | typical usage                        |
|-----------|---------------------|--------------------------------------|
| `day`     | `'1'` … `'31'`     | single month  e.g. Mar 2026          |
| `month`   | `'Jan'` … `'Dec'`  | single year   e.g. 2026              |
| `year`    | `'2022'` … `'2026'`| all-time — omit date params          |
 
The response includes pre-computed **totals** and **overall_completed_rate**.
    """,
)
def get_chart(
    breakdown: Literal["day", "month", "year"] = Query(
        "day",
        description="Aggregation granularity",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Inclusive start date  YYYY-MM-DD",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Inclusive end date    YYYY-MM-DD",
    ),
    impersonate: Optional[str] = Query(
        None,
        description="Admin only — view another user's chart data",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
        )
 
    username = _effective_username(current_user, impersonate)
 
    try:
        return crud_chart.get_chart_data(
            db=db,
            username=username,
            breakdown=breakdown,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
 
@router.get(
    "/recent-applications",
    response_model=RecentApplicationsResponse,
    summary="Most recent application log entries for the current user",
)
def get_recent_applications(
    limit: int = Query(
        default=10, ge=1, le=500,        # ← dagdag le=500 para puwedeng marami
        description="Number of rows to return",
    ),
    page: int = Query(
        default=1, ge=1,
        description="1-based page number",
    ),
    page_size: int = Query(
        default=10, ge=1, le=50,
        description="Rows per page (max 50)",
    ),
    impersonate: Optional[str] = Query(
        None, description="Admin only: view another user's data",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    username = _effective_username(current_user, impersonate)

    data = crud_recent.get_recent_applications(
        db=db,
        username=username,
        limit=limit,
        page=page,
        page_size=page_size,
    )

    return RecentApplicationsResponse(
        data=data["rows"],
        count=len(data["rows"]),
        total=data["total"],
        total_pages=data["total_pages"],
        page=data["page"],
        username=username,
    )
 
 
# ─────────────────────────────────────────────────────────────────────────────
# GET /api/dashboard/stats/detail
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/detail",
    response_model=MetricDetailResponse,
    summary="Paginated application log rows for a specific KPI metric",
    description="""
Returns the individual **ApplicationLog** rows that make up one of the three
KPI tiles on the dashboard.
 
| metric        | rows returned                                              |
|---------------|------------------------------------------------------------|
| `received`    | All rows for the user (any status, active threads only)    |
| `completed`   | Rows where `application_status = 'COMPLETED'`              |
| `on_process`  | Rows where `application_status = 'IN PROGRESS'`            |
 
Results are ordered newest-first and paginated (`page` / `page_size`).
    """,
)
def get_metric_detail(
    metric: str = Query(
        ...,
        description="KPI to drill into: received | completed | on_process",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Inclusive start date  YYYY-MM-DD",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Inclusive end date    YYYY-MM-DD",
    ),
    page: int = Query(
        default=1, ge=1,
        description="1-based page number",
    ),
    page_size: int = Query(
        default=10, ge=1, le=50,
        description="Rows per page (max 50)",
    ),
    impersonate: Optional[str] = Query(
        None,
        description="Admin only — view another user's data",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if metric not in ("received", "completed", "on_process"):
        raise HTTPException(
            status_code=422,
            detail="metric must be one of: received, completed, on_process",
        )
 
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be earlier than or equal to date_to.",
        )
 
    username = _effective_username(current_user, impersonate)
 
    try:
        return crud_detail.get_metric_detail(
            db=db,
            username=username,
            metric=metric,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    


@router.get(
    "/record-by-dtn",
    summary="Fetch a single MainDB record by DTN for ViewDetailsModal",
)
def get_record_by_dtn(
    dtn: str = Query(..., description="Document Tracking Number"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    record = db.query(MainDB).filter(
        MainDB.DB_DTN == int(dtn)
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return {
        "id": record.DB_ID,
        "mainDbId": record.DB_ID,
        "dtn": str(record.DB_DTN),
        "estCat": record.DB_EST_CAT,
        "ltoComp": record.DB_EST_LTO_COMP,
        "ltoAdd": record.DB_EST_LTO_ADD,
        "eadd": record.DB_EST_EADD,
        "tin": record.DB_EST_TIN,
        "contactNo": record.DB_EST_CONTACT_NO,
        "ltoNo": record.DB_EST_LTO_NO,
        "validity": record.DB_EST_VALIDITY,
        "prodBrName": record.DB_PROD_BR_NAME,
        "prodGenName": record.DB_PROD_GEN_NAME,
        "prodDosStr": record.DB_PROD_DOS_STR,
        "prodDosForm": record.DB_PROD_DOS_FORM,
        "prodClassPrescript": record.DB_PROD_CLASS_PRESCRIP,
        "prodEssDrugList": record.DB_PROD_ESS_DRUG_LIST,
        "prodPharmaCat": record.DB_PROD_PHARMA_CAT,
        "prodManu": record.DB_PROD_MANU,
        "prodManuAdd": record.DB_PROD_MANU_ADD,
        "prodManuTin": record.DB_PROD_MANU_TIN,
        "prodManuLtoNo": record.DB_PROD_MANU_LTO_NO,
        "prodManuCountry": record.DB_PROD_MANU_COUNTRY,
        "prodTrader": record.DB_PROD_TRADER,
        "prodTraderAdd": record.DB_PROD_TRADER_ADD,
        "prodTraderTin": record.DB_PROD_TRADER_TIN,
        "prodTraderLtoNo": record.DB_PROD_TRADER_LTO_NO,
        "prodTraderCountry": record.DB_PROD_TRADER_COUNTRY,
        "prodRepacker": record.DB_PROD_REPACKER,
        "prodRepackerAdd": record.DB_PROD_REPACKER_ADD,
        "prodRepackerTin": record.DB_PROD_REPACKER_TIN,
        "prodRepackerLtoNo": record.DB_PROD_REPACKER_LTO_NO,
        "prodRepackerCountry": record.DB_PROD_REPACKER_COUNTRY,
        "prodImporter": record.DB_PROD_IMPORTER,
        "prodImporterAdd": record.DB_PROD_IMPORTER_ADD,
        "prodImporterTin": record.DB_PROD_IMPORTER_TIN,
        "prodImporterLtoNo": record.DB_PROD_IMPORTER_LTO_NO,
        "prodImporterCountry": record.DB_PROD_IMPORTER_COUNTRY,
        "prodDistri": record.DB_PROD_DISTRI,
        "prodDistriAdd": record.DB_PROD_DISTRI_ADD,
        "prodDistriTin": record.DB_PROD_DISTRI_TIN,
        "prodDistriLtoNo": record.DB_PROD_DISTRI_LTO_NO,
        "prodDistriCountry": record.DB_PROD_DISTRI_COUNTRY,
        "prodDistriShelfLife": record.DB_PROD_DISTRI_SHELF_LIFE,
        "storageCond": record.DB_STORAGE_COND,
        "packaging": record.DB_PACKAGING,
        "suggRp": record.DB_SUGG_RP,
        "noSample": record.DB_NO_SAMPLE,
        "expiryDate": record.DB_EXPIRY_DATE,
        "cprValidity": record.DB_CPR_VALIDITY,
        "regNo": record.DB_REG_NO,
        "appType": record.DB_APP_TYPE,
        "motherAppType": record.DB_MOTHER_APP_TYPE,
        "oldRsn": record.DB_OLD_RSN,
        "ammend1": record.DB_AMMEND1,
        "ammend2": record.DB_AMMEND2,
        "ammend3": record.DB_AMMEND3,
        "prodCat": record.DB_PROD_CAT,
        "certification": record.DB_CERTIFICATION,
        "fee": record.DB_FEE,
        "lrf": record.DB_LRF,
        "surc": record.DB_SURC,
        "total": record.DB_TOTAL,
        "orNo": record.DB_OR_NO,
        "dateIssued": record.DB_DATE_ISSUED,
        "dateReceivedFdac": record.DB_DATE_RECEIVED_FDAC,
        "dateReceivedCent": record.DB_DATE_RECEIVED_CENT,
        "mo": record.DB_MO,
        "file": record.DB_FILE,
        "secpa": record.DB_SECPA,
        "secpaExpDate": record.DB_SECPA_EXP_DATE,
        "secpaIssuedOn": record.DB_SECPA_ISSUED_ON,
        "deckingSched": record.DB_DECKING_SCHED,
        "eval": record.DB_EVAL,
        "dateDeck": record.DB_DATE_DECK,
        "remarks1": record.DB_REMARKS_1,
        "dateRemarks": record.DB_DATE_REMARKS,
        "class": record.DB_CLASS,
        "dateReleased": record.DB_DATE_RELEASED,
        "typeDocReleased": record.DB_TYPE_DOC_RELEASED,
        "attaReleased": record.DB_ATTA_RELEASED,
        "cprCond": record.DB_CPR_COND,
        "cprCondRemarks": record.DB_CPR_COND_REMARKS,
        "cprCondAddRemarks": record.DB_CPR_COND_ADD_REMARKS,
        "appStatus": record.DB_APP_STATUS,
        "appRemarks": record.DB_APP_REMARKS,
        "userUploader": record.DB_USER_UPLOADER,
        "dateExcelUpload": str(record.DB_DATE_EXCEL_UPLOAD) if record.DB_DATE_EXCEL_UPLOAD else None,
        "pharmaProdCat": record.DB_PHARMA_PROD_CAT,
        "pharmaProdCatLabel": record.DB_PHARMA_PROD_CAT_LABEL,
        "dbTimelineCitizenCharter": record.DB_TIMELINE_CITIZEN_CHARTER,
        "processingType": record.DB_PROCESSING_TYPE,
    }

