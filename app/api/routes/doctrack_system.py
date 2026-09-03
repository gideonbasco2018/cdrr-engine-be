# app/api/routes/doctrack_system.py
"""
System-to-system Doctrack endpoints.
Authenticated via static Bearer token (EXTERNAL_DOCTRACK_TOKEN),
NOT via user login (get_current_active_user).

This is a separate router from doctrack.py's `router` on purpose —
that router requires a logged-in user session, which doesn't apply
to machine-to-machine callers.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.deps import DBSessionDep
from app.core.security_external import verify_doctrack_bearer_token
from app.crud.doctrack import (
    get_document_by_rsn,
    get_document_log_by_id,
)
from app.schemas.doctrack import DoctrackFullDetailsResponse

router = APIRouter(
    prefix="/api/doctrack",
    tags=["FIS - Document Tracking (System)"],
    dependencies=[Depends(verify_doctrack_bearer_token)],
)


@router.get("/full-details", response_model=DoctrackFullDetailsResponse)
def get_doctrack_full_details(
    db: DBSessionDep,
    rsn: str = Query(..., description="14-digit Doctrack Number"),
):
    """
    Combined endpoint for system-to-system access — a single call to get
    both the document info and all its logs, instead of calling two
    separate endpoints.

    Authenticated via static Bearer token (EXTERNAL_DOCTRACK_TOKEN).

    Flow:
      1. Look up the document using the RSN → get the docrecID
      2. Use the docrecID to look up all logs

    Sample: GET /api/doctrack/full-details?rsn=20260210154947
    Header: Authorization: Bearer <EXTERNAL_DOCTRACK_TOKEN>
    """
    documents = get_document_by_rsn(db, rsn)
    if not documents:
        raise HTTPException(status_code=404, detail=f"No document found for RSN {rsn}")

    document = documents[0]
    docrec_id = document.get("docrecID")

    if not docrec_id:
        raise HTTPException(
            status_code=500, detail=f"Document found for RSN {rsn} but missing docrecID"
        )

    logs = get_document_log_by_id(db, str(docrec_id)) or []

    return DoctrackFullDetailsResponse(
        rsn=rsn,
        docrecID=docrec_id,
        document=document,
        logs=logs,
        log_count=len(logs),
    )
