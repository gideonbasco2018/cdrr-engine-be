from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict

from app.core.deps import get_current_active_user
from app.db.deps import DBSessionDep
from app.crud.doctrack import (
    get_document_by_rsn,
    get_document_log_by_id,
    insert_document_log,
    insert_bulk_document_logs,
    get_document_logs_by_ids,
    get_docrecIDs_by_rsns
)
from app.schemas.doctrack import (
    BulkDocumentLogCreate,
    DocumentLogCreate,
    DocumentLogResponse
)

router = APIRouter(
    prefix="/api/doctrack",
    tags=["FIS - Document Tracking"],
    dependencies=[Depends(get_current_active_user)]  # 🔐 LOGIN REQUIRED BY DEFAULT
)

# ------------------------
# GET documents by RSN
# ------------------------
@router.get("/")
def get_document_tracking(
    db: DBSessionDep,
    rsn: str = Query(..., description="Document Tracking Number")
):
    result = get_document_by_rsn(db, rsn)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No document found for RSN {rsn}"
        )

    return {
        "count": len(result),
        "data": result
    }


# ------------------------
# GET document log by docrecID
# ------------------------
@router.get("/log")
def get_document_log(
    db: DBSessionDep,
    docrecID: str = Query(..., description="Document Receiving Log ID")
):
    result = get_document_log_by_id(db, docrecID)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No document log found for docrecID {docrecID}"
        )

    return {
        "count": len(result),
        "data": result
    }


# ------------------------
# POST insert document log
# ------------------------
@router.post("/log", response_model=DocumentLogResponse)
def create_document_log(
    log_data: DocumentLogCreate,
    db: DBSessionDep
):
    """
    Insert a new log into docreceivinglogtbl and return the inserted record.
    """
    inserted_log = insert_document_log(
        db=db,
        docrecID=log_data.docrecID,
        remarks=log_data.remarks,
        userID=log_data.userID
    )

    if not inserted_log:
        raise HTTPException(
            status_code=500,
            detail="Failed to create document log"
        )

    return inserted_log


# ------------------------
# POST bulk insert document logs
# ------------------------
@router.post("/docktrack/log/bulk", response_model=List[DocumentLogResponse])
def create_bulk_document_logs(
    bulk_data: BulkDocumentLogCreate,
    db: DBSessionDep
):
    """
    Insert multiple document logs at once.
    """
    logs_to_insert = [log.dict() for log in bulk_data.logs]

    inserted_logs = insert_bulk_document_logs(db, logs_to_insert)

    if not inserted_logs:
        raise HTTPException(
            status_code=500,
            detail="Failed to insert document logs"
        )

    return inserted_logs


# ------------------------
# GET bulk document logs
# ------------------------
@router.get("/docktrack/log/bulk", response_model=List[DocumentLogResponse])
def get_bulk_document_logs(
    db: DBSessionDep,
    docrecIDs: List[int] = Query(..., description="List of Document Receiving IDs")

):
    result = get_document_logs_by_ids(db, docrecIDs)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No document logs found for docrecIDs {docrecIDs}"
        )

    return result


# ------------------------
# GET bulk docrecIDs by RSNs
# ------------------------
@router.get("/docktrack/docrecids/bulk", response_model=List[Dict[str, int]])
def get_docrecIDs_bulk(
    db: DBSessionDep,
    rsns: List[str] = Query(..., description="List of RSNs")
):
    """
    Get all docrecIDs for multiple RSNs (for bulk log insertion).
    """
    result = get_docrecIDs_by_rsns(db, rsns)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No docrecIDs found for RSNs {rsns}"
        )

    return result
