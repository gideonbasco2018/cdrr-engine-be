from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, date

class DeckApplicationBase(BaseModel):
    decker: str = Field(..., description="Name of the person decking the application")
    evaluator: str = Field(..., description="Username of the assigned evaluator")
    deckerDecision: str = Field(..., description="Decision made by the decker")
    deckerRemarks: Optional[str] = Field(default="", description="Additional remarks")
    dateDeckedEnd: Optional[str] = Field(None, description="End date for decking in YYYY-MM-DD format")

class DeckApplicationRequest(DeckApplicationBase):
    pass

class BulkDeckApplicationRequest(DeckApplicationBase):
    record_ids: List[int] = Field(..., description="List of record IDs to deck")

class DeckApplicationResponse(BaseModel):
    success: bool
    message: str
    updated_count: int = 1
    
    class Config:
        from_attributes = True

class DeckRecordDetail(BaseModel):
    id: int
    dtn: Optional[str]
    evaluator: Optional[str]
    decker: Optional[str]
    deckerDecision: Optional[str]
    deckerRemarks: Optional[str]

    dateDeck: Optional[datetime]
    dateDeckedEnd: Optional[date]

    # Optional: other end dates
    dateEvalEnd: Optional[date]
    dateCheckerEnd: Optional[date]
    dateSupervisorEnd: Optional[date]
    dateQaEnd: Optional[date]
    dateDirectorEnd: Optional[date]

    class Config:
        from_attributes = True

    @validator(
        "dateDeckedEnd",
        "dateEvalEnd",
        "dateCheckerEnd",
        "dateSupervisorEnd",
        "dateQaEnd",
        "dateDirectorEnd",
        pre=True,
        always=True
    )
    def convert_datetime_to_date(cls, v):
        """Convert datetime to date if needed, keeps None safe"""
        if isinstance(v, datetime):
            return v.date()
        return v
    
class BulkDeckResponse(BaseModel):
    success: bool
    message: str
    updated_count: int
    failed_count: int
    details: Optional[List[dict]] = None

    class Config:
        from_attributes = True