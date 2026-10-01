# app/crud/e_app_documents.py
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.e_app_documents import EAppDocument
from app.schemas.e_app_documents import CPRAppDocumentCreate


def create_document(db: Session, payload: CPRAppDocumentCreate) -> EAppDocument:
    doc = EAppDocument(**payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document_by_id(db: Session, document_id: int) -> Optional[EAppDocument]:
    return (
        db.query(EAppDocument)
        .filter(EAppDocument.id == document_id, EAppDocument.is_deleted == 0)
        .first()
    )


def get_documents_by_application_uuid(
    db: Session, application_uuid: str, include_deleted: bool = False
) -> list[EAppDocument]:
    q = db.query(EAppDocument).filter(EAppDocument.application_uuid == application_uuid)
    if not include_deleted:
        q = q.filter(EAppDocument.is_deleted == 0)
    return q.order_by(EAppDocument.created_at.desc()).all()


def get_existing_folder_id(
    db: Session,
    application_uuid: str,
    requirement_group: str,
    category_code: Optional[str],
    requirement_code: str,
) -> Optional[str]:
    q = db.query(EAppDocument).filter(
        EAppDocument.application_uuid == application_uuid,
        EAppDocument.requirement_group == requirement_group,
        EAppDocument.requirement_code == requirement_code,
        EAppDocument.drive_folder_id.isnot(None),
    )
    if category_code and category_code.strip():
        q = q.filter(EAppDocument.category_code == category_code.strip())
    else:
        q = q.filter(EAppDocument.category_code.is_(None))
    doc = q.first()
    return doc.drive_folder_id if doc else None


def get_existing_document_by_name(
    db: Session,
    application_uuid: str,
    requirement_group: str,
    category_code: Optional[str],
    requirement_code: str,
    original_filename: str,
) -> Optional[EAppDocument]:
    q = db.query(EAppDocument).filter(
        EAppDocument.application_uuid == application_uuid,
        EAppDocument.requirement_group == requirement_group,
        EAppDocument.requirement_code == requirement_code,
        EAppDocument.original_filename == original_filename,
        EAppDocument.is_deleted == 0,
    )
    if category_code and category_code.strip():
        q = q.filter(EAppDocument.category_code == category_code.strip())
    else:
        q = q.filter(EAppDocument.category_code.is_(None))
    return q.first()


def overwrite_document(
    db: Session,
    doc: EAppDocument,
    *,
    drive_file_id: str,
    drive_file_url: str,
    drive_folder_id: Optional[str],
    mime_type: Optional[str],
    file_size_bytes: Optional[int],
    uploaded_by_user_uuid: Optional[str],
    uploaded_by_user_name: Optional[str],
) -> EAppDocument:
    doc.drive_file_id = drive_file_id
    doc.drive_file_url = drive_file_url
    doc.drive_folder_id = drive_folder_id
    doc.mime_type = mime_type
    doc.file_size_bytes = file_size_bytes
    doc.uploaded_by_user_uuid = uploaded_by_user_uuid
    doc.uploaded_by_user_name = uploaded_by_user_name
    db.commit()
    db.refresh(doc)
    return doc


def soft_delete_document(
    db: Session, document_id: int, deleted_by: Optional[str] = None
) -> Optional[EAppDocument]:
    doc = get_document_by_id(db, document_id)
    if not doc:
        return None
    doc.is_deleted = 1
    doc.deleted_at = datetime.now(timezone.utc)
    doc.deleted_by = deleted_by
    db.commit()
    db.refresh(doc)
    return doc
