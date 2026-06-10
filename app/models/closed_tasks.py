# app/models/closed_tasks.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ClosedTask(Base):
    __tablename__ = "closed_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ── Link to the application ───────────────────────────────────────
    main_db_id = Column(Integer, ForeignKey("main_db.DB_ID"), nullable=False, index=True)
    app_log_id = Column(Integer, ForeignKey("application_logs.id"), nullable=True)

    # ── Who closed it ─────────────────────────────────────────────────
    closed_by_user_id   = Column(Integer,     nullable=False)
    closed_by_user_name = Column(String(255), nullable=False)

    # ── Form fields from the modal ────────────────────────────────────
    reason_for_closing = Column(String(255), nullable=False)
    remarks            = Column(Text,        nullable=True)   # pure user remarks lang
    date_released      = Column(DateTime,    nullable=True)
    type_doc_released  = Column(String(100), nullable=True)

    # ── CPR Verification Portal audit (separate na, hindi nakaembed sa remarks) ──
    cpr_api_enabled       = Column(Boolean,     nullable=True)   # None = not CPR doc
    cpr_insert_success    = Column(Boolean,     nullable=True)   # True/False/None
    cpr_insert_error      = Column(Text,        nullable=True)   # error message kung failed
    cpr_skipped_by_user   = Column(Boolean,     nullable=False, default=False)  # OFF toggle

    # ── Timestamps ────────────────────────────────────────────────────
    closed_at  = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    main_db = relationship("MainDB",          foreign_keys=[main_db_id], lazy="select", viewonly=True)
    app_log = relationship("ApplicationLogs", foreign_keys=[app_log_id], lazy="select", viewonly=True)