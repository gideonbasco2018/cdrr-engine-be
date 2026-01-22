# app/schemas/analytics.py
from pydantic import BaseModel
from typing import Optional

class ReceivedCount(BaseModel):
    source: str  # FDAC or CENTRAL
    count: int

class ReceivedAnalyticsResponse(BaseModel):
    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    fdac: int
    central: int

    class Config:
        orm_mode = True
