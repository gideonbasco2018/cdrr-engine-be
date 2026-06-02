from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from app.db.session import get_db  # ✅ fixed import
from app.core.deps import get_current_active_user  # add if auth is needed

from app.schemas.doc_type_released import (
    DocTypeReleasedResponse,
    YearSummaryResponse,
)

router = APIRouter(
    prefix="/api/doc-type-released",  # consistent with other routes
    tags=["Document Type Released"],
    dependencies=[Depends(get_current_active_user)],  # add if auth is needed
)


@router.get("/", response_model=DocTypeReleasedResponse)
def get_doc_type_released(
    db: Session = Depends(get_db),
    app_type: Optional[str] = Query(None, description="Filter by DB_APP_TYPE"),
    year_from: Optional[int] = Query(None, description="Start year"),
    year_to: Optional[int] = Query(None, description="End year"),
):
    filters = [
        "DB_TYPE_DOC_RELEASED IS NOT NULL",
        "DB_TYPE_DOC_RELEASED != ''",
        "DB_DATE_RECEIVED_CENT IS NOT NULL",
        "DB_DATE_RECEIVED_CENT != ''",
    ]
    params: dict = {}

    if app_type:
        filters.append("DB_APP_TYPE = :app_type")
        params["app_type"] = app_type
    if year_from:
        filters.append("YEAR(STR_TO_DATE(DB_DATE_RECEIVED_CENT, '%Y-%m-%d')) >= :year_from")
        params["year_from"] = year_from
    if year_to:
        filters.append("YEAR(STR_TO_DATE(DB_DATE_RECEIVED_CENT, '%Y-%m-%d')) <= :year_to")
        params["year_to"] = year_to

    where = "WHERE " + " AND ".join(filters)

    sql = text(f"""
        SELECT
            YEAR(STR_TO_DATE(DB_DATE_RECEIVED_CENT, '%Y-%m-%d')) AS year,
            DB_TYPE_DOC_RELEASED                            AS doc_type,
            COUNT(*)                                        AS total
        FROM main_db
        {where}
        GROUP BY year, doc_type
        ORDER BY year ASC, doc_type ASC
    """)

    rows = db.execute(sql, params).fetchall()
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