# app/schemas/softcopy.py
"""Request bodies for the Softcopy routes."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SoftcopyDoctrackRequest(BaseModel):
    """FIS Doctrack update for the DTNs the user checked and confirmed."""
    dtns: List[str] = Field(..., max_length=500)
    remark: str


class SoftcopyDownloadCreate(BaseModel):
    """One Excel / PDF file downloaded from the page."""
    file_name: str = Field(..., min_length=1, max_length=255)
    file_type: Literal["xlsx", "pdf"]
    kind: Literal["Transmittal", "Export"]
    unit: Optional[str] = Field(None, max_length=100)
    dtns: List[str] = Field(default_factory=list, max_length=5000)
