# ============================================================
# FILE: app/models/menu_permissions.py
# ============================================================

from sqlalchemy import Column, Integer, String, Table, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from app.db.base_class import Base

# Association table for many-to-many relationship
menu_group_permissions = Table(  # ✅ PLURAL
    'menu_group_permissions',      # ✅ PLURAL (table name in DB)
    Base.metadata,
    Column('menu_id', Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
)

class MenuItem(Base):
    __tablename__ = "menu_items"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    path = Column(String(255), nullable=False)
    icon = Column(String(100), nullable=True)
    parent_id = Column(Integer, ForeignKey('menu_items.id', ondelete='CASCADE'), nullable=True)
    order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Many-to-many relationship with groups
    groups = relationship(
        "Group", 
        secondary=menu_group_permissions,  # ✅ PLURAL
        back_populates="menu_items"
    )
    
    # Self-referential relationship for nested menus
    children = relationship(
        "MenuItem",
        cascade="all, delete-orphan",
        single_parent=True,
        backref=backref(
            "parent",
            remote_side=[id]
        )
    )
    
    def __repr__(self):
        return f"<MenuItem(id={self.id}, menu_id='{self.menu_id}', name='{self.name}')>"