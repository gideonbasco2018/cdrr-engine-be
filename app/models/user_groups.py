from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True
    )

    joined_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # relationships
    user = relationship("User", back_populates="user_groups")
    group = relationship("Group", back_populates="user_groups")
