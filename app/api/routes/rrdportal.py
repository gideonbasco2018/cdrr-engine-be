# app/api/routes/rrdportal.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rrdportal_db import get_rrdportal_db
from app.crud import rrdportal as crud
from app.schemas.rrdportal import (
    CmdrInitialDetail,
    CmdrInitialPage,
    CmdrProductOut,
)

router = APIRouter(prefix="/api/rrdportal")


def _db_error(e: SQLAlchemyError) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Query failed: {type(e).__name__}")


@router.get("/health", tags=["RRD Portal"])
def rrdportal_health(db: Session = Depends(get_rrdportal_db)):
    """Verify the connection to wf_rrdportal."""
    try:
        db_name = db.execute(text("SELECT DATABASE()")).scalar()
        return {"status": "ok", "database": db_name}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to RRD Portal DB: {type(e).__name__}",
        )


# ======================= CMDR =======================


@router.get("/cmdr/initial", response_model=CmdrInitialPage, tags=["CMDR"])
def list_cmdr_initial(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Company name, DTN, or app number"),
    app_status: Optional[str] = None,
    db: Session = Depends(get_rrdportal_db),
):
    try:
        items, total = crud.get_cmdr_initial_list(
            db, skip=skip, limit=limit, search=search, app_status=app_status
        )
    except SQLAlchemyError as e:
        raise _db_error(e)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/cmdr/initial/{app_uid}", response_model=CmdrInitialDetail, tags=["CMDR"])
def get_cmdr_initial(app_uid: str, db: Session = Depends(get_rrdportal_db)):
    try:
        record = crud.get_cmdr_initial(db, app_uid)
        if record is None:
            raise HTTPException(status_code=404, detail="Application not found")
        record["products"] = crud.get_cmdr_products(db, app_uid)
    except SQLAlchemyError as e:
        raise _db_error(e)
    return record


@router.get(
    "/cmdr/initial/{app_uid}/products",
    response_model=List[CmdrProductOut],
    tags=["CMDR"],
)
def list_cmdr_products(app_uid: str, db: Session = Depends(get_rrdportal_db)):
    try:
        return crud.get_cmdr_products(db, app_uid)
    except SQLAlchemyError as e:
        raise _db_error(e)
