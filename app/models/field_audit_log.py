# app/models/field_audit_log.py

from sqlalchemy import (
    Column, Integer, String, Text, 
    DateTime, func
)
from app.db.base_class import Base


class ApplicationFieldAuditLog(Base):
    __tablename__ = "application_field_audit_logs"

    id            = Column(Integer, primary_key=True, index=True, autoincrement=True)
    main_db_id    = Column(Integer, nullable=False, index=True)   # ID ng main record
    log_id        = Column(Integer, nullable=True)                # ID ng application_log (kung meron)
    changed_by    = Column(String(150), nullable=False)           # username mula sa JWT
    changed_at    = Column(DateTime, server_default=func.now(), nullable=False)
    field_name    = Column(String(255), nullable=False)           # e.g. "prodBrName"
    field_label   = Column(String(255), nullable=True)            # e.g. "Brand Name"
    old_value     = Column(Text, nullable=True)                   # value bago i-edit
    new_value     = Column(Text, nullable=True)                   # value pagkatapos
    action_type   = Column(String(50), default="UPDATE")          # UPDATE | CREATE | DELETE
    step_context  = Column(String(100), nullable=True)            # e.g. "Checking"
    session_id    = Column(String(255), nullable=True, index=True) # groups changes per submit