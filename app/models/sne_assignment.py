# app/models/sne_assignment.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base_class import Base


class SneGenericAssignment(Base):
    """A generic-name keyword assigned to an S&E user (case-insensitive 'contains' match)."""

    __tablename__ = "sne_generic_assignments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    keyword = Column(String(100), nullable=False, index=True)  # stored lowercase
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_sne_user_keyword"),
    )
