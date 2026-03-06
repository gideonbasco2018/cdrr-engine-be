# ============================================================
# FILE: app/models/bulk_upload_history_records.py
# ============================================================

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class BulkUploadHistoryRecord(Base):
    __tablename__ = "bulk_upload_history_records"

    recordID  = Column(Integer,      primary_key=True, index=True, autoincrement=True)
    historyID = Column(Integer,      ForeignKey("bulk_upload_history.historyID", ondelete="CASCADE"), nullable=False, index=True)
    rowNum    = Column(Integer,      nullable=False)
    rsn       = Column(String(20),   nullable=False, index=True)
    remarks   = Column(String(1000), nullable=True)

    history = relationship("BulkUploadHistory", back_populates="records")

    def __repr__(self):
        return f"<BulkUploadHistoryRecord(id={self.recordID}, historyID={self.historyID}, rsn='{self.rsn}')>"