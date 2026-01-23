from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List

from app.schemas.group import GroupCreate, GroupResponse
from app.crud import group as crud_group
from app.db.session import get_db
from app.models.group import Group

router = APIRouter(
    prefix="/api/group",
    tags=["Groups"]
)

@router.get("/test")
def test_endpoint():
    return {"message": "Group router is working!"}

@router.get("/db-test")
def test_db(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).fetchone()
        return {"status": "Database connected", "result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(group_in: GroupCreate, db: Session = Depends(get_db)):
    existing = db.query(Group).filter_by(name=group_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group name already exists")
    return crud_group.create(db, group_in)

@router.get("/", response_model=List[GroupResponse])
def list_groups(db: Session = Depends(get_db)):
    return crud_group.get_all(db)
