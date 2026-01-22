from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from datetime import datetime

class ApplicationDelegation(Base):
    __tablename__ = "application_delegation"

    # Primary Key
    ID = Column(Integer, primary_key=True, autoincrement=True)

    # 1-to-1 link to MainDB
    DB_MAIN_ID = Column(
        Integer,
        ForeignKey("main_db.DB_ID", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="FK to MainDB"
    )

    # ------------------------- Decker Information -------------------------
    DB_DECKER = Column(Text, nullable=True, comment="Decker Name")
    DB_DECKER_DECISION = Column(Text, nullable=True, comment="Decker Decision")
    DB_DECKER_REMARKS = Column(Text, nullable=True, comment="Decker Remarks")
    DB_DATE_DECKED_END = Column(DateTime, nullable=True, comment="Date Decked End")  # Updated

    # ------------------------- Evaluator Information -------------------------
    DB_EVALUATOR = Column(Text, nullable=True, comment="Evaluator Name")
    DB_EVAL_DECISION = Column(Text, nullable=True, comment="Evaluator Decision")
    DB_EVAL_REMARKS = Column(Text, nullable=True, comment="Evaluator Remarks")
    DB_DATE_EVAL_END = Column(DateTime, nullable=True, comment="Date Evaluation End")  # Updated

    # ------------------------- Checker Information -------------------------
    DB_CHECKER = Column(Text, nullable=True, comment="Checker Name")
    DB_CHECKER_DECISION = Column(Text, nullable=True, comment="Checker Decision")
    DB_CHECKER_REMARKS = Column(Text, nullable=True, comment="Checker Remarks")
    DB_DATE_CHECKER_END = Column(DateTime, nullable=True, comment="Date Checker End")  # Updated

    # ------------------------- Supervisor Information -------------------------
    DB_SUPERVISOR = Column(Text, nullable=True, comment="Supervisor Name")
    DB_SUPERVISOR_DECISION = Column(Text, nullable=True, comment="Supervisor Decision")
    DB_SUPERVISOR_REMARKS = Column(Text, nullable=True, comment="Supervisor Remarks")
    DB_DATE_SUPERVISOR_END = Column(DateTime, nullable=True, comment="Date Supervisor End")  # Updated

    # ------------------------- QA Information -------------------------
    DB_QA = Column(Text, nullable=True, comment="QA Name")
    DB_QA_DECISION = Column(Text, nullable=True, comment="QA Decision")
    DB_QA_REMARKS = Column(Text, nullable=True, comment="QA Remarks")
    DB_DATE_QA_END = Column(DateTime, nullable=True, comment="Date QA End")  # Updated

    # ------------------------- Director Information -------------------------
    DB_DIRECTOR = Column(Text, nullable=True, comment="Director Name")
    DB_DIRECTOR_DECISION = Column(Text, nullable=True, comment="Director Decision")
    DB_DIRECTOR_REMARKS = Column(Text, nullable=True, comment="Director Remarks")
    DB_DATE_DIRECTOR_END = Column(DateTime, nullable=True, comment="Date Director End")  # Updated

        # ------------------------- Releasing Officer Information -------------------------
    DB_RELEASING_OFFICER = Column(Text, nullable=True, comment="Releasing Officer Name")
    DB_RELEASING_OFFICER_DECISION = Column(Text, nullable=True, comment="Releasing Officer Decision")
    DB_RELEASING_OFFICER_REMARKS = Column(Text, nullable=True, comment="Releasing Officer Remarks")
    DB_RELEASING_OFFICER_END = Column(DateTime, nullable=True, comment="Date Releasing Officer End")  # Updated

    # Relationship back to MainDB
    main = relationship(
        "MainDB",
        back_populates="application_delegation",
        uselist=False
    )

    def __repr__(self):
        return f"<ApplicationDelegation(main_id={self.DB_MAIN_ID})>"
