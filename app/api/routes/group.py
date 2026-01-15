from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.group import GroupCreate, GroupResponse
from app.crud import group as crud_group
from app.db.session import get_db

router = APIRouter(
    prefix="/api/group",
    tags=["Groups"]
)


@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(group_in: GroupCreate, db: Session = Depends(get_db)):
    # Optional: check if group name already exists
    existing = db.query(crud_group.Group).filter_by(name=group_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group name already exists")

    return crud_group.create(db, group_in)

@router.get("/", response_model=List[GroupResponse])
def list_groups(db: Session = Depends(get_db)):
    return crud_group.get_all(db)
