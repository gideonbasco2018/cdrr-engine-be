from sqlalchemy.orm import Session
from app.models.group import Group
from app.schemas.group import GroupCreate

def create(db: Session, group_in: GroupCreate) -> Group:
    db_group = Group(name=group_in.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_all(db: Session):
    return db.query(Group).all()

def get_by_id(db: Session, group_id: int):
    return db.query(Group).filter(Group.id == group_id).first()
