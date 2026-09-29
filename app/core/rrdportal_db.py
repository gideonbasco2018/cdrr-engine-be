# app/core/rrdportal_db.py
from typing import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

rrdportal_engine = None
RrdportalSessionLocal = None

if settings.REMOTE_FDA_RRDPORTAL_URL:
    rrdportal_engine = create_engine(
        settings.REMOTE_FDA_RRDPORTAL_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 5},  # fail fast if unreachable
    )
    RrdportalSessionLocal = sessionmaker(
        bind=rrdportal_engine,
        autocommit=False,
        autoflush=False,
    )


def get_rrdportal_db() -> Generator[Session, None, None]:
    """Yield a session bound to the wf_rrdportal database."""
    if RrdportalSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="RRD Portal database is not configured.",
        )

    db = RrdportalSessionLocal()
    try:
        yield db
    finally:
        db.close()
