# app/api/routes/eservices_drug_group_summary.py
import logging
from typing import List, Optional

from app.core.deps import get_current_active_user
from app.models.user import User, UserRole

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.eservices_drug_groups import DRUG_GROUPS
from app.core.eservices_cpr_drugs_db import get_eservices_cpr_drugs_db
from app.crud.eservices_drug_group_summary import (
    get_drug_group_generic_names,
    get_drug_group_records,
    get_drug_group_summary,
)
from app.schemas.eservices_drug_group_summary import (
    ApplicationStatus,
    ApplicationStep,
    DrugGroupGenericName,
    DrugGroupGenericNamesResponse,
    DrugGroupInfo,
    DrugGroupRecord,
    DrugGroupRecordsResponse,
    DrugGroupSummaryResponse,
)

logger = logging.getLogger(__name__)


def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Allow only admin and superadmin users."""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only.",
        )
    return current_user


router = APIRouter(
    prefix="/api/reports",
    tags=["EServices Reports"],
    dependencies=[Depends(get_current_active_user)],
)


def _resolve_group(group: str):
    """Return (group_key, drug_group) or raise 404 for an unknown group."""
    group_key = group.strip().lower()
    drug_group = DRUG_GROUPS.get(group_key)

    if drug_group is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown drug group '{group}'. Available: {', '.join(DRUG_GROUPS)}",
        )
    return group_key, drug_group


@router.get("/drug-groups", response_model=List[DrugGroupInfo])
def list_drug_groups():
    """List the available drug groups (useful for a frontend dropdown)."""
    return [{"key": key, "label": group["label"]} for key, group in DRUG_GROUPS.items()]


@router.get("/drug-group-summary", response_model=DrugGroupSummaryResponse)
def read_drug_group_summary(
    group: str = Query(..., description="Drug group key, e.g. tuberculosis or cancer"),
    application_status: ApplicationStatus = Query(
        ApplicationStatus.COMPLETED,
        description="Latest application log status: Pending or Completed",
    ),
    application_step: Optional[ApplicationStep] = Query(
        None,
        description="Optional current step filter, e.g. APPROVAL",
    ),
    db: Session = Depends(get_eservices_cpr_drugs_db),
):
    """Per-drug counts and overall totals for CLIDP applications of a drug group."""
    group_key, drug_group = _resolve_group(group)

    try:
        summary = get_drug_group_summary(
            db,
            drug_group,
            application_status.value,
            application_step.value if application_step else None,
        )
    except SQLAlchemyError:
        logger.exception("Failed to query the remote cpr_drugs database")
        raise HTTPException(
            status_code=502,
            detail="Failed to query the remote cpr_drugs database.",
        )

    return {
        "group": group_key,
        "application_status": application_status.value,
        **summary,
    }


@router.get(
    "/drug-group-records/generic-names",
    response_model=DrugGroupGenericNamesResponse,
    summary="Distinct generic names of a drug group (multi-select options)",
)
def read_drug_group_generic_names(
    group: str = Query(...),
    application_status: ApplicationStatus = Query(ApplicationStatus.COMPLETED),
    application_step: Optional[ApplicationStep] = Query(None),
    db: Session = Depends(get_eservices_cpr_drugs_db),
):
    _, drug_group = _resolve_group(group)

    try:
        items = get_drug_group_generic_names(
            db,
            drug_group,
            application_status.value,
            application_step.value if application_step else None,
        )
    except SQLAlchemyError:
        logger.exception("Failed to query the remote cpr_drugs database")
        raise HTTPException(
            status_code=502,
            detail="Failed to query the remote cpr_drugs database.",
        )

    return DrugGroupGenericNamesResponse(
        data=[DrugGroupGenericName(**item) for item in items]
    )


@router.get(
    "/drug-group-records",
    response_model=DrugGroupRecordsResponse,
    summary="Application records (one row per product) behind a drug group total",
)
def read_drug_group_records(
    group: str = Query(...),
    application_status: ApplicationStatus = Query(ApplicationStatus.COMPLETED),
    application_step: Optional[ApplicationStep] = Query(None),
    search: Optional[str] = Query(None),
    generic_names: Optional[List[str]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_eservices_cpr_drugs_db),
):
    _, drug_group = _resolve_group(group)

    try:
        rows, total = get_drug_group_records(
            db,
            drug_group,
            application_status.value,
            application_step.value if application_step else None,
            search=search,
            generic_names=generic_names,
            page=page,
            page_size=page_size,
        )
    except SQLAlchemyError:
        logger.exception("Failed to query the remote cpr_drugs database")
        raise HTTPException(
            status_code=502,
            detail="Failed to query the remote cpr_drugs database.",
        )

    return DrugGroupRecordsResponse(
        data=[DrugGroupRecord(**row) for row in rows], total=total
    )
