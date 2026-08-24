# api/routes/cpr_applications.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security_external import verify_bearer_token

from app.schemas.cpr_applications import ApplicationCreate, ApplicationResponse
from app.crud import cpr_applications as crud_application

router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.post(
    "/",
    response_model=ApplicationResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    return crud_application.create_application(db, payload)
