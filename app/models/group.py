# ============================================================
# FILE: app/models/group.py
# ============================================================

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255), nullable=True)

    # association object relationship (existing)
    user_groups = relationship(
        "UserGroup",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    # convenience access (Group.users) (existing)
    users = relationship(
        "User",
        secondary="user_groups",
        viewonly=True
    )
    
    # Many-to-many relationship with menu items
    menu_items = relationship(
        "MenuItem", 
        secondary="menu_group_permissions",  # ✅ PLURAL
        back_populates="groups"
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"