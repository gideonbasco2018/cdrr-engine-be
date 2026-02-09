from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class DeckApplicationBase(BaseModel):
    decker: str = Field(..., description="Name of the person decking the application")
    evaluator: str = Field(..., description="Username of the assigned evaluator")
    deckerDecision: str = Field(..., description="Decision made by the decker")
    deckerRemarks: Optional[str] = Field(default="", description="Additional remarks")
    dateDeckedEnd: Optional[str] = Field(None, description="ISO datetime string")

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
    dtn: Optional[str] = None
    evaluator: Optional[str] = None
    decker: Optional[str] = None
    deckerDecision: Optional[str] = None
    deckerRemarks: Optional[str] = None
    dateDeckedEnd: Optional[datetime] = None  # ✅ Changed to datetime
    
    # Optional: other end dates
    dateEvalEnd: Optional[datetime] = None
    dateCheckerEnd: Optional[datetime] = None
    dateSupervisorEnd: Optional[datetime] = None
    dateQaEnd: Optional[datetime] = None
    dateDirectorEnd: Optional[datetime] = None
    dateReleasingOfficerEnd: Optional[datetime] = None

    class Config:
        from_attributes = True
        # This will automatically serialize datetime with timezone
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class BulkDeckResponse(BaseModel):
    success: bool
    message: str
    updated_count: int
    failed_count: int
    details: Optional[List[dict]] = None

    class Config:
        from_attributes = True