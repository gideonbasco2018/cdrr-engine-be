# app/models/bulk_upload_log.py

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.base_class import Base


class BulkUploadLog(Base):
    """
    Audit log ng bawat file sa isang bulk/folder upload operation.
    Isang 'batch_id' = isang upload-folder (o upload-batch) call.
    Nilo-log natin LAHAT ng files (success at failed), para may
    complete na picture kung anong nangyari sa buong batch.
    """
    __tablename__ = "bulk_upload_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Groups all log entries na galing sa parehong upload call
    batch_id = Column(String(36), nullable=False, index=True)

    main_db_id    = Column(Integer, nullable=True, index=True)
    db_entry_type = Column(String(255), nullable=False, index=True)
    db_dtn        = Column(String(255), nullable=False, index=True)
    doc_category  = Column(String(255), nullable=True)

    original_filename = Column(String(500), nullable=False)
    relative_path      = Column(Text, nullable=True)  # webkitRelativePath, kung meron

    # "success" | "failed"
    status        = Column(String(20), nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    mime_type       = Column(String(100), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Link papunta sa naimbak na document, kung successful ang upload
    application_document_id = Column(
        Integer,
        ForeignKey("application_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    uploaded_by_user_id   = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    uploaded_by_user_name = Column(String(255), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return (
            f"<BulkUploadLog(id={self.id}, batch_id={self.batch_id}, "
            f"filename={self.original_filename}, status={self.status})>"
        )