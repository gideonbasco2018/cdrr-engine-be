from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    # association object relationship
    user_groups = relationship(
        "UserGroup",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    # convenience access (Group.users)
    users = relationship(
        "User",
        secondary="user_groups",
        viewonly=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
