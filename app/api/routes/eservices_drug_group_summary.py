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
from app.crud.eservices_drug_group_summary import get_drug_group_summary
from app.schemas.eservices_drug_group_summary import (
    ApplicationStatus,
    ApplicationStep,
    DrugGroupInfo,
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
    group_key = group.strip().lower()
    drug_group = DRUG_GROUPS.get(group_key)

    if drug_group is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown drug group '{group}'. Available: {', '.join(DRUG_GROUPS)}",
        )

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
