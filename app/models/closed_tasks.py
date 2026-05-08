# app/models/closed_tasks.py
"""
Closed Tasks Model
Permanently closed tasks — this action cannot be undone.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base  # adjust import to match your project


class ClosedTask(Base):
    __tablename__ = "closed_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ── Link to the application ───────────────────────────────────────
    main_db_id = Column(Integer, ForeignKey("main_db.DB_ID"), nullable=False, index=True)

    # ── The application log that was active when closing ──────────────
    app_log_id = Column(Integer, ForeignKey("application_logs.id"), nullable=True)

    # ── Who closed it ─────────────────────────────────────────────────
    closed_by_user_id   = Column(Integer,     nullable=False)
    closed_by_user_name = Column(String(255), nullable=False)

    # ── Form fields from the modal ────────────────────────────────────
    reason_for_closing = Column(String(255), nullable=False)
    remarks            = Column(Text,        nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────
    closed_at  = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    # viewonly=True + no back_populates → no need to touch MainDB or ApplicationLogs models
    main_db = relationship("MainDB",          foreign_keys=[main_db_id], lazy="select", viewonly=True)
    app_log = relationship("ApplicationLogs", foreign_keys=[app_log_id], lazy="select", viewonly=True)