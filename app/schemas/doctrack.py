from pydantic import BaseModel, Field
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
    logs: List[DocumentLogCreate] = Field(..., description="List of document logs to insert")


# Response schema for single/bulk log

class DocumentLogResponse(BaseModel):
    logID: int
    docrecID: int
    logdate: datetime
    remarks: str
    userID: Optional[int] = None