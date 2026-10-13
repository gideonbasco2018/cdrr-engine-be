# app/schemas/gmp_post_eval_status.py
# Response shapes for the FGMP Dashboard's "Post-Evaluation Status" card.

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PostEvalStatusStepCount(BaseModel):
    """One header chip. `step` is the display label — a step name for
    anything that moved forward, or a return label ("Returned by Checker",
    "Sent back — not checked", "For Compliance") for anything that came back
    — and doubles as the `bucket` the list endpoint filters on. `group` is
    which header the card renders it under."""
    step: str
    count: int
    group: str  # "returned" | "forward"


class PostEvalStatusSummaryResponse(BaseModel):
    """The card header's chip rows: returns first, then the forward steps in
    workflow order."""
    breakdown: List[PostEvalStatusStepCount]
    total: int


class PostEvalStatusRow(BaseModel):
    gmp_id: int
    dtn: Optional[str] = None
    lto_company: Optional[str] = None
    your_step: Optional[str] = None
    completed_date: Optional[datetime] = None
    current_step: Optional[str] = None
    # Set only when the application is sitting back on the step this user last
    # completed, and says who sent it back. None means it moved forward and
    # current_step is what to show.
    return_reason: Optional[str] = None


class PostEvalStatusListResponse(BaseModel):
    data: List[PostEvalStatusRow]
    total: int
    total_pages: int
    page: int
