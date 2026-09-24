# app/models/cpr_generated_document.py

import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRGeneratedDocument(Base):
    __tablename__ = "cpr_generated_documents"

    doc_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_uuid = Column(
        String(36),
        ForeignKey("cpr_application.application_uuid"),
        nullable=False,
        index=True,
    )

    # "ORDER_OF_PAYMENT" | "CERTIFICATE" | "NOTICE_OF_DEFICIENCY" atbp.
    document_type = Column(String(50), nullable=False, index=True)

    # Kung kailan mo need i-trace pabalik sa specific OP row
    source_uuid = Column(String(36), nullable=True, index=True)  # e.g. op_uuid

    drive_file_id = Column(String(255), nullable=False)
    drive_file_url = Column(Text, nullable=False)
    drive_folder_id = Column(String(255), nullable=True)

    generated_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    generated_at = Column(DateTime, server_default=func.now())

    application = relationship("CPRApplication", backref="generated_documents")
