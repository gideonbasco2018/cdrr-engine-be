from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint

from app.db.base_class import Base  # ADAPT: your declarative Base


class WorkflowRoleGroup(Base):
    __tablename__ = "workflow_role_groups"

    id = Column(Integer, primary_key=True)
    role_key = Column(String(50), nullable=False, index=True)
    # ADAPT: real table name of your groups table
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (UniqueConstraint("role_key", "group_id"),)
