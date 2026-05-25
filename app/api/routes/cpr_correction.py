from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.cpr_correction import DTNVerifyRequest, DTNVerifyResponse, CorrectionSubmitRequest, CorrectionSubmitResponse
from app.crud.cpr_correction import verify_dtn, submit_correction

router = APIRouter(
    prefix="/api/cpr-correction",
    tags=["CPR Correction"],
)


@router.post(
    "/verify-dtn",
    response_model=DTNVerifyResponse,
    summary="Verify DTN for CPR Correction",
    description=(
        "Looks up the given DTN in main_db. "
        "Returns found/eligible status and full application details "
        "only when DB_APP_STATUS = 'COMPLETED'."
    ),
)
def verify_dtn_endpoint(
    payload: DTNVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DTNVerifyResponse:
    if not payload.dtn or not payload.dtn.strip():
        raise HTTPException(status_code=422, detail="DTN cannot be empty.")

    return verify_dtn(dtn=payload.dtn, db=db)


@router.post(
    "/submit-correction",
    response_model=CorrectionSubmitResponse,
    summary="Submit CPR Correction",
    description=(
        "Inserts a new MainDB record with the corrected DTN and updated fields. "
        "Re-validates that the original DTN is still COMPLETED before inserting."
    ),
)
def submit_correction_endpoint(
    payload: CorrectionSubmitRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> CorrectionSubmitResponse:
    if not payload.old_dtn.strip() or not payload.new_dtn.strip():
        raise HTTPException(status_code=422, detail="Both old_dtn and new_dtn are required.")

    return submit_correction(payload=payload, db=db, current_user=current_user)