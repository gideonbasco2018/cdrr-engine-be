# app/schemas/gmp_post_eval_status.py
# Response shapes for the FGMP Dashboard's "Post-Evaluation Status" card.

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PostEvalStatusStepCount(BaseModel):
    step: str
    count: int


class PostEvalStatusSummaryResponse(BaseModel):
    """Per-current-step breakdown, e.g. QA Admin: 1, Checker: 5,
    OD Releasing: 3 — the card header's chip row."""
    breakdown: List[PostEvalStatusStepCount]
    total: int


class PostEvalStatusRow(BaseModel):
    gmp_id: int
    dtn: Optional[str] = None
    lto_company: Optional[str] = None
    your_step: Optional[str] = None
    completed_date: Optional[datetime] = None
    current_step: Optional[str] = None


class PostEvalStatusListResponse(BaseModel):
    data: List[PostEvalStatusRow]
    total: int
    total_pages: int
    page: int
