# app/schemas/sne_assignment.py
from typing import List, Optional, Dict
from pydantic import BaseModel


class WorkloadOut(BaseModel):
    user_id: int
    total: int
    by_step: Dict[str, int]


class SneMemberOut(BaseModel):
    id: int
    username: str
    first_name: str
    surname: str
    keywords: List[str]


class SneKeywordsIn(BaseModel):
    keywords: List[str]


class SuggestItemIn(BaseModel):
    id: int  # main_db id of the record
    generic_name: Optional[str] = None


class SuggestIn(BaseModel):
    items: List[SuggestItemIn]


class SuggestItemOut(BaseModel):
    id: int
    user_id: Optional[int] = None  # None = no matching rule
    matched_keyword: Optional[str] = None


class SuggestOut(BaseModel):
    assignments: List[SuggestItemOut]


class SneAssignmentCreate(BaseModel):
    user_id: int
    keyword: str


class SneAssignmentOut(BaseModel):
    id: int
    user_id: int
    keyword: str

    class Config:
        orm_mode = True  # pydantic v2: from_attributes = True
