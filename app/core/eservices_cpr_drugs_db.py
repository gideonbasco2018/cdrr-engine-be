# app/core/eservices_cpr_drugs_db.py
from typing import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

eservices_cpr_drugs_engine = None
EservicesCprDrugsSessionLocal = None

if settings.REMOTE_FDA_CPR_DRUGS_ESERVICES_URL:
    eservices_cpr_drugs_engine = create_engine(
        settings.REMOTE_FDA_CPR_DRUGS_ESERVICES_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    EservicesCprDrugsSessionLocal = sessionmaker(
        bind=eservices_cpr_drugs_engine,
        autocommit=False,
        autoflush=False,
    )


def get_eservices_cpr_drugs_db() -> Generator[Session, None, None]:
    """Yield a session bound to the eServices AWS cpr_drugs database."""
    if EservicesCprDrugsSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="eServices cpr_drugs database is not configured.",
        )

    db = EservicesCprDrugsSessionLocal()
    try:
        yield db
    finally:
        db.close()
