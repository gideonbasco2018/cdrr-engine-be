# app/routers/field_audit_log.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.field_audit_log import (
    CreateFieldAuditLogRequest,
    FieldAuditLogResponse,
    AuditSession,
)
from app.core.deps import get_current_active_user
from app.crud import field_audit_log as crud_audit   # ← CRUD import


router = APIRouter(
    prefix="/api/field-audit-logs",
    tags=["Field Audit Logs"],
)


# ---------------------------------------------------------------
# POST — I-save ang lahat ng changes sa isang submit
# ---------------------------------------------------------------
@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_field_audit_logs(
    payload:      CreateFieldAuditLogRequest,
    db:           Session = Depends(get_db),
    current_user          = Depends(get_current_active_user),
):
    if not payload.changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No changes provided.",
        )

    return crud_audit.create_field_audit_logs(
        db          = db,
        payload     = payload,
        changed_by  = current_user.username,
    )


# ---------------------------------------------------------------
# GET — Audit history ng isang record (grouped by session)
# ---------------------------------------------------------------
@router.get("/{main_db_id}", response_model=List[AuditSession])
def get_audit_history(
    main_db_id:  int,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_active_user),
):
    return crud_audit.get_audit_history_by_record(db=db, main_db_id=main_db_id)


# ---------------------------------------------------------------
# GET — Lahat ng edits ng isang user
# ---------------------------------------------------------------
@router.get("/by-user/{username}", response_model=List[FieldAuditLogResponse])
def get_audit_by_user(
    username:    str,
    limit:       int     = 50,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_active_user),
):
    return crud_audit.get_audit_logs_by_user(db=db, username=username, limit=limit)


# ---------------------------------------------------------------
# GET — Single session drill-down
# ---------------------------------------------------------------
@router.get("/session/{session_id}", response_model=List[FieldAuditLogResponse])
def get_audit_by_session(
    session_id:  str,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_active_user),
):
    return crud_audit.get_audit_logs_by_session(db=db, session_id=session_id)


# ---------------------------------------------------------------
# GET — Count ng edits ng isang record (para sa badge sa UI)
# ---------------------------------------------------------------
@router.get("/count/{main_db_id}", response_model=dict)
def get_audit_count(
    main_db_id:  int,
    db:          Session = Depends(get_db),
    current_user         = Depends(get_current_active_user),
):
    count = crud_audit.get_audit_count_by_record(db=db, main_db_id=main_db_id)
    return {"main_db_id": main_db_id, "total_changes": count}
