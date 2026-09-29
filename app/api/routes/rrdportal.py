# app/api/routes/rrdportal.py
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rrdportal_db import get_rrdportal_db
from app.crud import rrdportal as crud
from app.schemas.rrdportal import (
    CmdrAllPage,
    CmdrApplicationDetail,
    CmdrApplicationPage,
    CmdrDelegationOut,
    CmdrFilterOptions,
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


class CmdrType(str, Enum):
    initial = "initial"
    initial_abridge = "initial_abridge"
    renewal = "renewal"
    amendment = "amendment"


# NOTE: /cmdr/all and /cmdr/all/filters must stay ABOVE the /cmdr/{app_type}
# routes, otherwise "all" would be treated as an app_type.


@router.get("/cmdr/all", response_model=CmdrAllPage, tags=["CMDR"])
def list_cmdr_all(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Company name, DTN, or app number"),
    app_status: Optional[str] = None,
    type_application: Optional[str] = Query(None, description="Exact TYPE_APPLICATION"),
    application_option: Optional[str] = Query(
        None, description="Exact APPLICATION_OPTION"
    ),
    cmdr_type: Optional[List[CmdrType]] = Query(
        None,
        description="Limit to these tables. Repeat the param: ?cmdr_type=renewal&cmdr_type=amendment",
    ),
    include_products: bool = Query(
        False, description="Nest each application's products"
    ),
    include_delegations: bool = Query(
        False, description="Nest each application's APP_DELEGATION rows"
    ),
    db: Session = Depends(get_rrdportal_db),
):
    """All CMDR tables in one list. Each row has CMDR_TYPE telling where it came from."""
    try:
        items, total = crud.get_cmdr_all(
            db,
            skip=skip,
            limit=limit,
            search=search,
            app_status=app_status,
            type_application=type_application,
            application_option=application_option,
            types=[t.value for t in cmdr_type] if cmdr_type else None,
            include_products=include_products,
            include_delegations=include_delegations,
        )
    except SQLAlchemyError as e:
        raise _db_error(e)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/cmdr/all/filters", response_model=CmdrFilterOptions, tags=["CMDR"])
def cmdr_filter_options(db: Session = Depends(get_rrdportal_db)):
    """Distinct TYPE_APPLICATION / APPLICATION_OPTION / APP_STATUS values (for dropdowns)."""
    try:
        return crud.get_cmdr_filter_options(db)
    except SQLAlchemyError as e:
        raise _db_error(e)


@router.get("/cmdr/{app_type}", response_model=CmdrApplicationPage, tags=["CMDR"])
def list_cmdr(
    app_type: CmdrType,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Company name, DTN, or app number"),
    app_status: Optional[str] = None,
    type_application: Optional[str] = Query(None, description="Exact TYPE_APPLICATION"),
    application_option: Optional[str] = Query(
        None, description="Exact APPLICATION_OPTION"
    ),
    include_products: bool = Query(
        False, description="Nest each application's products"
    ),
    include_delegations: bool = Query(
        False, description="Nest each application's APP_DELEGATION rows"
    ),
    db: Session = Depends(get_rrdportal_db),
):
    try:
        items, total = crud.get_cmdr_list(
            db,
            app_type.value,
            skip=skip,
            limit=limit,
            search=search,
            app_status=app_status,
            type_application=type_application,
            application_option=application_option,
            include_products=include_products,
            include_delegations=include_delegations,
        )
    except SQLAlchemyError as e:
        raise _db_error(e)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get(
    "/cmdr/{app_type}/{app_uid}", response_model=CmdrApplicationDetail, tags=["CMDR"]
)
def get_cmdr(app_type: CmdrType, app_uid: str, db: Session = Depends(get_rrdportal_db)):
    try:
        record = crud.get_cmdr_application(db, app_type.value, app_uid)
        if record is None:
            raise HTTPException(status_code=404, detail="Application not found")
        record["products"] = crud.get_cmdr_products(db, app_type.value, app_uid)
        record["delegations"] = crud.get_cmdr_delegations(db, app_uid)
    except SQLAlchemyError as e:
        raise _db_error(e)
    return record


@router.get(
    "/cmdr/{app_type}/{app_uid}/products",
    response_model=List[CmdrProductOut],
    tags=["CMDR"],
)
def list_cmdr_products(
    app_type: CmdrType, app_uid: str, db: Session = Depends(get_rrdportal_db)
):
    try:
        return crud.get_cmdr_products(db, app_type.value, app_uid)
    except SQLAlchemyError as e:
        raise _db_error(e)


@router.get(
    "/cmdr/{app_type}/{app_uid}/delegations",
    response_model=List[CmdrDelegationOut],
    tags=["CMDR"],
)
def list_cmdr_delegations(
    app_type: CmdrType, app_uid: str, db: Session = Depends(get_rrdportal_db)
):
    """APP_DELEGATION rows of one application, ordered by DEL_INDEX."""
    try:
        return crud.get_cmdr_delegations(db, app_uid)
    except SQLAlchemyError as e:
        raise _db_error(e)
