from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.cpr_correction import DTNVerifyRequest, DTNVerifyResponse
from app.crud.cpr_correction import verify_dtn

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