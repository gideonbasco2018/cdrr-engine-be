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


class SingleDoctrackLogByRsnRequest(BaseModel):
    rsn: str = Field(..., description="14-digit Doctrack Number")
    remarks: str = Field(..., description="Remarks text")
    userID: int = Field(..., description="User ID creating the log")

class BulkDoctrackLogByRsnRequest(BaseModel):
    entries: List[SingleDoctrackLogByRsnRequest] = Field(..., description="List of RSN + remarks + userID")
    
# Response schema for single/bulk log

class DocumentLogResponse(BaseModel):
    logID: int
    docrecID: int
    logdate: datetime
    remarks: str
    userID: Optional[int] = None