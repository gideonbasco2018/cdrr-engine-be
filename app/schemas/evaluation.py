from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date

class EvaluationBase(BaseModel):
    """Base schema for evaluation data"""
    evaluator: str = Field(..., min_length=1, max_length=100, description="Evaluator username (DB_EVALUATOR)")
    eval_decision: str = Field(..., min_length=1, max_length=50, description="Evaluation decision (DB_EVAL_DECISION)")
    eval_remarks: Optional[str] = Field(default="", max_length=1000, description="Evaluation remarks (DB_EVAL_REMARKS)")
    date_eval_end: Optional[str] = Field(None, description="Evaluation end date YYYY-MM-DD (DB_DATE_EVAL_END)")
    checker: Optional[str] = Field(default=None, max_length=100, description="Assign to checker for next stage (DB_CHECKER)")

    @field_validator('date_eval_end')
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format is YYYY-MM-DD"""
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v

    @field_validator('eval_decision')
    @classmethod
    def validate_decision(cls, v: str) -> str:
        """Validate evaluation decision is not empty"""
        if not v or not v.strip():
            raise ValueError('Evaluation decision cannot be empty')
        return v.strip()


class EvaluationRequest(EvaluationBase):
    """Schema for single evaluation request"""
    pass


class BulkEvaluationRequest(EvaluationBase):
    """Schema for bulk evaluation request"""
    record_ids: List[int] = Field(..., min_length=1, description="List of record IDs to evaluate")

    @field_validator('record_ids')
    @classmethod
    def validate_record_ids(cls, v: List[int]) -> List[int]:
        """Validate record IDs are unique and positive"""
        if not v:
            raise ValueError('At least one record ID is required')
        
        if len(v) != len(set(v)):
            raise ValueError('Duplicate record IDs are not allowed')
        
        if any(rid <= 0 for rid in v):
            raise ValueError('All record IDs must be positive integers')
        
        return v


class EvaluationResponse(BaseModel):
    """Schema for single evaluation response"""
    success: bool
    message: str
    updated_count: int = 1


class BulkEvaluationDetail(BaseModel):
    """Schema for individual record details in bulk evaluation"""
    id: int
    status: str  # 'success' or 'failed'
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class BulkEvaluationResponse(BaseModel):
    """Schema for bulk evaluation response"""
    success: bool
    message: str
    updated_count: int
    failed_count: int
    details: List[BulkEvaluationDetail] = []

    class Config:
        from_attributes = True


class EvaluationRecordDetail(BaseModel):
    """Schema for evaluation record details"""
    id: int
    dtn: Optional[str] = None
    evaluator: Optional[str] = None
    eval_decision: Optional[str] = None
    eval_remarks: Optional[str] = None
    date_eval_end: Optional[date] = None

    class Config:
        from_attributes = True

    @field_validator("date_eval_end", mode='before')
    @classmethod
    def convert_datetime_to_date(cls, v):
        """Convert datetime to date if needed"""
        if isinstance(v, datetime):
            return v.date()
        return v