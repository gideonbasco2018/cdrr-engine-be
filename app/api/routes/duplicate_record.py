# app/api/routes/duplicate_record.py

import math
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.crud import duplicate_record as crud_duplicate
from app.db.session import get_db
from app.models.user import User
from app.schemas.duplicate_record import (
    DuplicateGroup,
    DuplicateRecordsResponse,
)

router = APIRouter(
    prefix="/api/duplicate-records",
    tags=["Duplicate Records"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("", response_model=DuplicateRecordsResponse)
def get_duplicates(
    by: Literal["dtn", "reg_no"] = Query(
        ..., description="Field to check duplicates on"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Records per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Tumukoy ng totoong duplicate records sa buong main_db table
    (hindi lang sa current page) — base sa DTN o Registration No.

    Pinaginate ang `records` (default 50/page, max 200/page) para
    hindi sumabog ang response size sa malaking dataset.
    """
    dupe_groups, records, total_count = crud_duplicate.get_duplicate_records(
        db, by, page=page, page_size=page_size
    )

    total_pages = math.ceil(total_count / page_size) if total_count else 0

    return DuplicateRecordsResponse(
        by=by,
        duplicate_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        groups=[
            DuplicateGroup(dupe_key=str(g.dupe_key), count=g.cnt)
            for g in dupe_groups
        ],
        records=records,
    )