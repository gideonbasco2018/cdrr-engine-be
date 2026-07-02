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
    """Kunin yung drive_folder_id kung meron nang existing document na
    parehong db_entry_type + db_dtn + doc_category, para hindi na mag-search/create ulit."""
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