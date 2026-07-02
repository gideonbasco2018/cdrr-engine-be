# app/api/routes/doc_type_released.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from typing import Optional

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.doc_type_released import get_doc_type_released_rows
from app.schemas.doc_type_released import (
    DocTypeReleasedResponse,
    YearSummaryResponse,
)

router = APIRouter(
    prefix="/api/doc-type-released",
    tags=["Document Type Released"],
    dependencies=[Depends(get_current_active_user)],
)


# ─────────────────────────────────────────────
# GET /api/doc-type-released/
# Yearly breakdown of released documents per doc type
# ─────────────────────────────────────────────

@router.get("/", response_model=DocTypeReleasedResponse)
def get_doc_type_released(
    db: Session = Depends(get_db),
    app_type: Optional[str] = Query(None, description="Filter by DB_APP_TYPE"),
    year_from: Optional[int] = Query(None, description="Start year"),
    year_to: Optional[int] = Query(None, description="End year"),
):
    """
    Get yearly summary of released documents grouped by doc type.

    Returns a list of unique doc types (for dynamic table columns) plus
    a per-year breakdown showing total released, count per doc type,
    and CPR release rate.

    Optional filters:
    - app_type: restrict to a specific DB_APP_TYPE
    - year_from / year_to: restrict to a year range (inclusive)

    Rows with missing/blank doc type or unparseable DB_DATE_RECEIVED_CENT
    are excluded from the aggregation.
    """
    rows = get_doc_type_released_rows(
        db=db, app_type=app_type, year_from=year_from, year_to=year_to
    )

    doc_types = sorted({r.doc_type for r in rows if r.doc_type})

    year_map: dict = {}
    for r in rows:
        yr = str(r.year)
        if yr not in year_map:
            year_map[yr] = {"year": yr, "total": 0, "by_doc_type": {}}
        year_map[yr]["by_doc_type"][r.doc_type] = int(r.total)
        year_map[yr]["total"] += int(r.total)

    summaries = []
    for yr, d in sorted(year_map.items()):
        cpr = d["by_doc_type"].get("CPR", 0)
        rate = round((cpr / d["total"]) * 100, 1) if d["total"] else 0.0
        summaries.append(YearSummaryResponse(
            year=d["year"], total=d["total"],
            by_doc_type=d["by_doc_type"], rate=rate,
        ))

    return DocTypeReleasedResponse(doc_types=doc_types, data=summaries)