# app/crud/application_document.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.application_document import ApplicationDocument
from app.schemas.application_document import ApplicationDocumentCreate


def create_document(
    db: Session,
    payload: ApplicationDocumentCreate,
) -> ApplicationDocument:
    """Create a new application document record and persist it to the DB."""
    doc = ApplicationDocument(**payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_documents_by_main_db_id(
    db: Session,
    main_db_id: int,
    include_deleted: bool = False,
) -> list[ApplicationDocument]:
    """Return all documents linked to a given application (main_db_id),
    most recently created first. Excludes soft-deleted documents unless
    include_deleted is True."""
    q = db.query(ApplicationDocument).filter(
        ApplicationDocument.main_db_id == main_db_id
    )
    if not include_deleted:
        q = q.filter(ApplicationDocument.is_deleted == 0)
    return q.order_by(ApplicationDocument.created_at.desc()).all()


def get_document_by_id(
    db: Session,
    document_id: int,
) -> Optional[ApplicationDocument]:
    """Fetch a single non-deleted document by its primary key."""
    return (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.id == document_id,
            ApplicationDocument.is_deleted == 0,
        )
        .first()
    )


def soft_delete_document(
    db: Session,
    document_id: int,
    deleted_by: Optional[str] = None,
) -> Optional[ApplicationDocument]:
    """Mark a document as deleted (is_deleted flag) without removing the
    DB row itself, recording who deleted it and when. Returns None if no
    matching non-deleted document is found."""
    doc = get_document_by_id(db, document_id)
    if not doc:
        return None
    doc.is_deleted = 1
    doc.deleted_at = datetime.now(timezone.utc)
    doc.deleted_by = deleted_by
    db.commit()
    db.refresh(doc)
    return doc

def get_existing_folder_id(
    db: Session,
    db_entry_type: str,
    db_dtn: str,
    doc_category: Optional[str] = None,
) -> Optional[str]:
    """Look up the Google Drive folder ID already associated with this
    entry_type/dtn/category combination, based on any existing document
    record that points to it. Returns None if no matching folder has been
    recorded yet, in which case the caller should create one."""
    q = (
        db.query(ApplicationDocument)
        .filter(ApplicationDocument.db_entry_type == db_entry_type)
        .filter(ApplicationDocument.db_dtn == db_dtn)
        .filter(ApplicationDocument.drive_folder_id.isnot(None))
    )

    if doc_category and doc_category.strip():
        q = q.filter(ApplicationDocument.doc_category == doc_category.strip())
    else:
        q = q.filter(ApplicationDocument.doc_category.is_(None))

    doc = q.first()
    return doc.drive_folder_id if doc else None


def get_existing_document_by_name(
    db: Session,
    db_entry_type: str,
    db_dtn: str,
    doc_category: Optional[str],
    original_filename: str,
) -> Optional[ApplicationDocument]:
    """Find an existing non-deleted document that matches the same
    entry_type/dtn/category and has the same original filename. Used to
    detect duplicates so an upload can overwrite the existing file/record
    instead of creating a new one."""
    q = (
        db.query(ApplicationDocument)
        .filter(ApplicationDocument.db_entry_type == db_entry_type)
        .filter(ApplicationDocument.db_dtn == db_dtn)
        .filter(ApplicationDocument.original_filename == original_filename)
        .filter(ApplicationDocument.is_deleted == 0)
    )
    if doc_category and doc_category.strip():
        q = q.filter(ApplicationDocument.doc_category == doc_category.strip())
    else:
        q = q.filter(ApplicationDocument.doc_category.is_(None))
    return q.first()


def overwrite_document(
    db: Session,
    doc: ApplicationDocument,
    *,
    drive_file_id: str,
    drive_file_url: str,
    drive_folder_id: Optional[str],
    mime_type: Optional[str],
    file_size_bytes: Optional[int],
    uploaded_by_user_id: Optional[int],
    uploaded_by_user_name: Optional[str],
) -> ApplicationDocument:
    """Update an existing document record in place with new Drive file
    details (used when a re-uploaded file replaces a prior version with
    the same filename, instead of creating a duplicate record)."""
    doc.drive_file_id = drive_file_id
    doc.drive_file_url = drive_file_url
    doc.drive_folder_id = drive_folder_id
    doc.mime_type = mime_type
    doc.file_size_bytes = file_size_bytes
    doc.uploaded_by_user_id = uploaded_by_user_id
    doc.uploaded_by_user_name = uploaded_by_user_name
    db.commit()
    db.refresh(doc)
    return doc

def get_documents_by_dtn(
    db: Session,
    db_dtn: str,
    include_deleted: bool = False,
) -> list[ApplicationDocument]:
    """Return all documents linked to a given DTN, across all entry types
    and document categories, most recently created first. Excludes
    soft-deleted documents unless include_deleted is True."""
    q = db.query(ApplicationDocument).filter(
        ApplicationDocument.db_dtn == db_dtn
    )
    if not include_deleted:
        q = q.filter(ApplicationDocument.is_deleted == 0)
    return q.order_by(ApplicationDocument.created_at.desc()).all()