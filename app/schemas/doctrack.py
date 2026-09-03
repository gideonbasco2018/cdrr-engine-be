# app/schemas/doctrack.py
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List


# ------------------------
# Request schemas
# ------------------------
class DocumentLogCreate(BaseModel):
    docrecID: int = Field(..., description="Document Receiving ID")
    remarks: str = Field(..., description="Remarks for the log")
    userID: int = Field(..., description="User ID creating the log")


class BulkDocumentLogCreate(BaseModel):
    logs: List[DocumentLogCreate] = Field(
        ..., description="List of document logs to insert"
    )


class SingleDoctrackLogByRsnRequest(BaseModel):
    rsn: str = Field(..., description="14-digit Doctrack Number")
    remarks: str = Field(..., description="Remarks text")
    userID: int = Field(..., description="User ID creating the log")
    alias: str = Field(
        default="", description="User alias to append to remarks"
    )  # ← DAGDAG

    @validator("rsn", pre=True)
    def coerce_rsn_to_str(cls, v):
        return str(v)


class BulkDoctrackLogByRsnRequest(BaseModel):
    entries: List[SingleDoctrackLogByRsnRequest] = Field(
        ..., description="List of RSN + remarks + userID"
    )
    alias: str = Field(default="", description="User alias to append to remarks")


# Response schema
class DocumentLogResponse(BaseModel):
    logID: int
    docrecID: int
    logdate: datetime
    remarks: str
    userID: Optional[int] = None

    class Config:
        from_attributes = True  # para sa Pydantic v2 (dating orm_mode = True)


# ─────────────────────────────────────────────
# System-to-system: combined RSN → docrecID → logs lookup
# ─────────────────────────────────────────────
class DoctrackFullDetailsResponse(BaseModel):
    rsn: str
    docrecID: int
    document: dict
    logs: List[dict]
    log_count: int

    class Config:
        from_attributes = True
