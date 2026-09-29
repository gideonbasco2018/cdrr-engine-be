# app/crud/rrdportal.py
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.rrdportal import CmdrInitialOut, CmdrProductOut


def _cols(model) -> str:
    """Build the SELECT list from the schema; backticks protect reserved words like ROW."""
    return ", ".join(f"`{name}`" for name in model.model_fields)


# ======================= CMDR =======================

CMDR_INITIAL_TABLE = "PMT_CMDR_INITIAL"
CMDR_PRODUCT_TABLE = "PMT_CMDR_INITIAL_PRODUCT"
CMDR_INITIAL_COLS = _cols(CmdrInitialOut)
CMDR_PRODUCT_COLS = _cols(CmdrProductOut)


def get_cmdr_initial_list(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    conditions: List[str] = []
    params: Dict[str, Any] = {"skip": skip, "limit": limit}

    if search:
        conditions.append(
            "(COMPANY_NAME LIKE :search OR DTN LIKE :search "
            "OR CAST(APP_NUMBER AS CHAR) LIKE :search)"
        )
        params["search"] = f"%{search}%"

    if app_status:
        conditions.append("APP_STATUS = :app_status")
        params["app_status"] = app_status

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = (
        db.execute(
            text(f"SELECT COUNT(*) FROM {CMDR_INITIAL_TABLE} {where}"), params
        ).scalar()
        or 0
    )

    rows = (
        db.execute(
            text(
                f"SELECT {CMDR_INITIAL_COLS} FROM {CMDR_INITIAL_TABLE} {where} "
                "ORDER BY APP_NUMBER DESC LIMIT :limit OFFSET :skip"
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows], total


def get_cmdr_initial(db: Session, app_uid: str) -> Optional[Dict[str, Any]]:
    row = (
        db.execute(
            text(
                f"SELECT {CMDR_INITIAL_COLS} FROM {CMDR_INITIAL_TABLE} "
                "WHERE APP_UID = :uid"
            ),
            {"uid": app_uid},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_cmdr_products(db: Session, app_uid: str) -> List[Dict[str, Any]]:
    rows = (
        db.execute(
            text(
                f"SELECT {CMDR_PRODUCT_COLS} FROM {CMDR_PRODUCT_TABLE} "
                "WHERE APP_UID = :uid ORDER BY `ROW`"
            ),
            {"uid": app_uid},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
