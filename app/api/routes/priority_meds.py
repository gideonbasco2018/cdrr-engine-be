# app/api/routes/priority_meds.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User

import app.crud.priority_meds as crud
from app.schemas.priority_meds import (
    PharmaCategoryBreakdownResponse,
    VaccineBreakdownResponse,
)

router = APIRouter(
    prefix="/api/monitoring/priority-meds",
    tags=["Priority Meds Monitoring"],
)


# ══════════════════════════════════════════════════════════════════════
#  GET /monitoring/priority-meds/cancer
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/cancer",
    response_model=PharmaCategoryBreakdownResponse,
    summary="Cancer meds breakdown (in-progress applications)",
)
def cancer_meds_breakdown(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    items = crud.get_cancer_meds_breakdown(db)
    grand_total = sum(item.total_pending for item in items)
    return PharmaCategoryBreakdownResponse(items=items, grand_total=grand_total)


# ══════════════════════════════════════════════════════════════════════
#  GET /monitoring/priority-meds/rare-disease
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/rare-disease",
    response_model=PharmaCategoryBreakdownResponse,
    summary="Rare disease meds breakdown (in-progress applications)",
)
def rare_disease_breakdown(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    items = crud.get_rare_disease_breakdown(db)
    grand_total = sum(item.total_pending for item in items)
    return PharmaCategoryBreakdownResponse(items=items, grand_total=grand_total)


# ══════════════════════════════════════════════════════════════════════
#  GET /monitoring/priority-meds/flu-vaccines
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/flu-vaccines",
    response_model=VaccineBreakdownResponse,
    summary="Flu vaccine breakdown (in-progress applications)",
)
def flu_vaccine_breakdown(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    items = crud.get_flu_vaccine_breakdown(db)
    grand_total = sum(item.total_count for item in items)
    return VaccineBreakdownResponse(items=items, grand_total=grand_total)


# ══════════════════════════════════════════════════════════════════════
#  GET /monitoring/priority-meds/pneumococcal
# ══════════════════════════════════════════════════════════════════════
@router.get(
    "/pneumococcal",
    response_model=VaccineBreakdownResponse,
    summary="Pneumococcal vaccine breakdown (in-progress applications)",
)
def pneumococcal_breakdown(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    items = crud.get_pneumococcal_breakdown(db)
    grand_total = sum(item.total_count for item in items)
    return VaccineBreakdownResponse(items=items, grand_total=grand_total)
