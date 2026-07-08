# app/models/task_targets.py

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base

class TaskTarget(Base):
    __tablename__ = "task_targets"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Kanino ba ang target - user o team level
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)  # kung meron kang teams table

    # Scope ng target (para ma-filter later, e.g. "Evaluation", "Decking")
    task_type = Column(String(100), nullable=True, index=True)

    # Period
    period_type = Column(String(20), nullable=False)   # 'daily' | 'weekly' | 'monthly'
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)

    target_count = Column(Integer, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())