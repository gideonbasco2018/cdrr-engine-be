# app/api/routes/gmp_record.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
import math
import io
from app.db.session import get_db
from app.schemas.gmp_record import (
    GMPRecordCreate, GMPRecordUpdate, GMPRecordResponse, GMPRecordListResponse,
    GMPRecordSummary, GMPApplicationLogResponse, GMPFieldAuditLogResponse,
    GMPAdvanceStepRequest, GMPTaskListResponse,
    GMPApplicationLogUpdate, GMPReassignRequest, GMPRerouteRequest,
    GMPAddIssuanceRequest, GMPIssuanceFieldsUpdate,
)
from app.crud import gmp_record as crud
from app.crud import gmp_logs
from app.crud.gmp_record import (
    get_gmp_records, get_gmp_logs, GMP_LOG_STEPS, GMP_STEP_DEL_INDEX, GMP_ACTION_ROUTES,
)
from app.models.gmp_record import GMPRecord
from app.core.deps import get_current_active_user
from app.models.user import User

router = APIRouter(
    prefix="/api/gmp",
    tags=["GMP Queue"],
    dependencies=[Depends(get_current_active_user)],
)

def _full_name(user) -> Optional[str]:
    first = getattr(user, "first_name", None) or ""
    last  = getattr(user, "surname", None) or ""
    full  = f"{first} {last}".strip()
    return full or None

# ──────────────────────────────────────────────────────────────────────────────
# IMPORTANT: All static / literal-segment routes MUST come before /{record_id}.
# FastAPI matches routes in declaration order. If /{record_id} (int) appears
# first, every request to /filter-counts, /tasks, /summary, /log-steps,
# /audit-logs/*, /logs/* will 422 because those strings can't be cast to int.
# ──────────────────────────────────────────────────────────────────────────────


# ── Template download (static — must be before /{record_id}) ─────────────────
@router.get("/template", summary="Download GMP Excel upload template")
def download_template():
    from app.api.routes.gmp_upload import _build_template_workbook
    output = _build_template_workbook()
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="GMP_Upload_Template.xlsx"'},
    )


# ── List records ──────────────────────────────────────────────────────────────
@router.get("/", response_model=GMPRecordListResponse)
def get_gmp_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    dtns: Optional[str] = Query(None, description="Comma-separated DTN numbers"),
    tab: Optional[str] = Query(None, description="all | not_yet_decked | decked"),
    view: Optional[str] = Query(None, description="main (one row per DTN) | omit for all reference numbers"),
    duplicates_only: Optional[bool] = Query(None, description="Only DTNs whose reference records share a duplicate Type of Issuance"),
    app_status: Optional[str] = Query(None),
    est_category: Optional[str] = Query(None),
    pics_nonpics: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    type_of_issuance: Optional[str] = Query(None),
    current_step: Optional[str] = Query(None),
    evaluator: Optional[str] = Query(None),
    dtn: Optional[int] = Query(None),
    related_dtn: Optional[str] = Query(None),
    lto_company: Optional[str] = Query(None),
    uploaded_by: Optional[str] = Query(None),
    upload_date_from: Optional[str] = Query(None),
    upload_date_to: Optional[str] = Query(None),
    date_received_from: Optional[str] = Query(None),
    date_received_to: Optional[str] = Query(None),
    sort_by: str = Query("GMP_DATE_EXCEL_UPLOAD"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * page_size
    parsed_dtns = []
    if dtns:
        for raw in dtns.split(","):
            raw = raw.strip()
            if raw.isdigit():
                parsed_dtns.append(int(raw))

    filters = {
        "tab": tab, "view": view, "duplicates_only": duplicates_only, "app_status": app_status, "est_category": est_category,
        "pics_nonpics": pics_nonpics, "transaction_type": transaction_type,
        "type_of_issuance": type_of_issuance, "current_step": current_step,
        "evaluator": evaluator, "dtn": dtn,
        "dtns": parsed_dtns if parsed_dtns else None,
        "related_dtn": related_dtn,
        "lto_company": lto_company,
        "uploaded_by": uploaded_by,
        "upload_date_from": upload_date_from,
        "upload_date_to": upload_date_to,
        "date_received_from": date_received_from,
        "date_received_to": date_received_to,
    }

    records, total = get_gmp_records(
        db=db, skip=skip, limit=page_size, search=search,
        filters=filters, sort_by=sort_by, sort_order=sort_order,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "total": total, "page": page, "page_size": page_size,
        "total_pages": total_pages, "data": records,
    }


# ── Filter counts for sidebar (static — must be before /{record_id}) ──────────
@router.get("/filter-counts")
def get_gmp_filter_counts(
    tab: Optional[str] = Query(None, description="'decked' | 'not_yet_decked' | omit for All Reports"),
    view: Optional[str] = Query(None, description="main (one row per DTN) | omit for all reference numbers"),
    db: Session = Depends(get_db),
):
    not_trashed = or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted")
    primary_base = crud._primary_only(db.query(GMPRecord).filter(not_trashed))
    # Mirrors get_gmp_records: "All Reports" + view=main (or omitted "view")
    # each drive whether "total" (and the TopTabs "All" badge) is counted
    # with every reference number as its own row, or one row per DTN.
    # "Decked"/"Not Yet Decked" key off workflow state, which only the
    # primary ('-01') reference ever carries, so those stay primary-only
    # regardless of view.
    total = primary_base.count() if view == "main" else db.query(GMPRecord).filter(not_trashed).count()
    decked_ids = crud._decked_subquery(db)
    decked = primary_base.filter(
        or_(GMPRecord.GMP_ID.in_(decked_ids), GMPRecord.GMP_APP_STATUS == "COMPLETED")
    ).count()
    not_yet_decked = primary_base.filter(
        GMPRecord.GMP_ID.notin_(decked_ids),
        or_(GMPRecord.GMP_APP_STATUS != "COMPLETED", GMPRecord.GMP_APP_STATUS.is_(None)),
    ).count()

    # The "All" option inside each group, and each value's own count, need to
    # match whichever tab is actually active — otherwise the numbers next to
    # a sidebar option don't add up to what clicking it actually returns.
    tab_total = {"decked": decked, "not_yet_decked": not_yet_decked}.get(tab, total)

    # Per-group dot colors — each group gets a distinct accent
    GROUP_COLORS = {
        "app_status":       {
            "ON-PROCESS":  "#3b82f6",
            "COMPLETED":   "#10b981",
            "PENDING":     "#f59e0b",
            "FOR DECKING": "#06b6d4",
            "DECKED":      "#6366f1",
            "DISAPPROVED": "#ef4444",
            "IN PROGRESS": "#f97316",
        },
        "est_category":     "#f59e0b",   # amber
        "transaction_type": "#8b5cf6",   # purple
        "type_of_issuance": "#06b6d4",   # cyan
    }

    def _colored_group(field, label, key, empty_value=None, empty_label="(Empty)"):
        raw_items = crud.get_field_counts(db, field, tab=tab, view=view, empty_value=empty_value, empty_label=empty_label)
        color_map = GROUP_COLORS.get(key, "#94a3b8")
        colored = []
        for item in raw_items:
            if isinstance(color_map, dict):
                c = color_map.get((item["value"] or "").upper(), "#94a3b8")
            else:
                c = color_map
            colored.append({**item, "color": c})
        return {
            "label": label, "key": key,
            "items": [{"value": "all", "label": "All", "count": tab_total, "color": "#94a3b8"}] + colored,
        }

    return {
        "total": total, "not_yet_decked": not_yet_decked, "decked": decked,
        "groups": [
            # "__EMPTY__" mirrors the sentinel get_gmp_records already
            # accepts for app_status — without it, records with no status
            # set yet are invisible in this sidebar (dropped silently)
            # despite counting toward "All".
            _colored_group("GMP_APP_STATUS",       "Application Status", "app_status",
                            empty_value="__EMPTY__", empty_label="No Status"),
            _colored_group("GMP_EST_CATEGORY",     "Category",           "est_category"),
            _colored_group("GMP_TRANSACTION_TYPE", "Transaction Type",   "transaction_type"),
            _colored_group("GMP_TYPE_OF_ISSUANCE", "Issuance Type",      "type_of_issuance"),
        ],
    }


# ── Summary (static — must be before /{record_id}) ────────────────────────────
@router.get("/summary", response_model=GMPRecordSummary)
def get_summary(db: Session = Depends(get_db)):
    return crud.get_gmp_summary(db)


# ── Log step definitions (static) ─────────────────────────────────────────────
@router.get("/log-steps")
def get_log_steps():
    return {"steps": [{"label": label, "del_index": idx} for label, idx in GMP_LOG_STEPS]}


# ── Tasks for current user (static — must be before /{record_id}) ─────────────
@router.get("/tasks", response_model=GMPTaskListResponse)
def get_my_gmp_tasks(
    application_step: Optional[str] = Query(None),
    is_received: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    username = getattr(current_user, "username", None)
    if not username:
        return {"total": 0, "page": page, "page_size": page_size, "total_pages": 0, "data": []}
    logs, total = gmp_logs.get_tasks_for_user(
        db, username, application_step, is_received, page, page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "total": total, "page": page, "page_size": page_size,
        "total_pages": total_pages, "data": logs,
    }

# ── Task count for current user (static — must be before /{record_id}) ───────
@router.get("/tasks/my-task-count")
def get_my_gmp_task_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    username = getattr(current_user, "username", None)
    if not username:
        return {"count": 0}
    count = gmp_logs.get_task_count_for_user(db, username)
    return {"count": count}


# ── Mark task received (static prefix /logs/ — must be before /{record_id}) ───
@router.patch("/logs/{log_id}/receive", response_model=GMPApplicationLogResponse)
def mark_task_received(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    username = getattr(current_user, "username", None)
    log = gmp_logs.mark_received(db, log_id, username)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Log {log_id} not found")
    return log


# ── Toggle star (static prefix /logs/) ────────────────────────────────────────
@router.patch("/logs/{log_id}/star", response_model=GMPApplicationLogResponse)
def toggle_task_star(
    log_id: int,
    starred: bool = Query(..., description="true = star, false = unstar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    log = gmp_logs.toggle_star(db, log_id, starred)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Log {log_id} not found")
    return log


# ── Field audit logs (static prefix /audit-logs/ — before /{record_id}) ───────
@router.get("/audit-logs/session/{session_id}", response_model=List[GMPFieldAuditLogResponse])
def get_field_audit_logs_for_session(
    session_id: str, db: Session = Depends(get_db)
):
    return crud.get_field_audit_logs_by_session(db, session_id)


@router.get("/audit-logs/{record_id}", response_model=List[GMPFieldAuditLogResponse])
def get_field_audit_logs(
    record_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * page_size
    logs, _ = crud.get_field_audit_logs(
        db=db, gmp_record_id=record_id, skip=skip, limit=page_size,
    )
    return logs


# ── Create record (POST /) ─────────────────────────────────────────────────────
@router.post("/", response_model=GMPRecordResponse, status_code=status.HTTP_201_CREATED)
def create_record(
    record: GMPRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return crud.create_gmp_record(
        db, record,
        user_name=getattr(current_user, "username", None),
        user_id=getattr(current_user, "id", None),
    )


# ── Single record — GET / PUT / DELETE /{record_id} ───────────────────────────
@router.get("/{record_id}", response_model=GMPRecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    record = crud.get_gmp_record(db, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"GMP record {record_id} not found")
    return record


@router.put("/{record_id}", response_model=GMPRecordResponse)
def update_record(
    record_id: int,
    record_update: GMPRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    updated = crud.update_gmp_record(
        db, record_id, record_update,
        user_name=getattr(current_user, "username", None),
        user_id=getattr(current_user, "id", None),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"GMP record {record_id} not found")
    return updated


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int,
    hard_delete: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if hard_delete:
        success = crud.hard_delete_gmp_record(db, record_id)
    else:
        success = crud.delete_gmp_record(
            db, record_id,
            user_name=getattr(current_user, "username", None),
            user_id=getattr(current_user, "id", None),
        )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"GMP record {record_id} not found")
    return None


# ── Add issuance (duplicate record under same DTN, new issuance type) ────────
@router.post("/{record_id}/add-issuance", response_model=GMPRecordResponse, status_code=status.HTTP_201_CREATED)
def add_issuance(
    record_id: int,
    req: GMPAddIssuanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    new_record = crud.add_gmp_issuance(
        db, record_id, req.type_of_issuance,
        user_name=getattr(current_user, "username", None),
        user_id=getattr(current_user, "id", None),
    )
    if not new_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"GMP record {record_id} not found or has no DTN to duplicate under.",
        )
    return new_record


# ── Sibling reference numbers under the same DTN ──────────────────────────────
@router.get("/{record_id}/siblings", response_model=List[GMPRecordResponse])
def get_siblings(record_id: int, db: Session = Depends(get_db)):
    return crud.get_gmp_siblings(db, record_id)


# ── Update issuance-specific fields on a single reference number ──────────────
@router.patch("/{record_id}/issuance-fields", response_model=GMPRecordResponse)
def update_issuance_fields(
    record_id: int,
    req: GMPIssuanceFieldsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    updated = crud.update_gmp_issuance_fields(
        db, record_id,
        type_of_issuance=req.type_of_issuance,
        certificate_number=req.certificate_number,
        certificate_validity=req.certificate_validity,
        secpa_number=req.secpa_number,
        user_name=getattr(current_user, "username", None),
        user_id=getattr(current_user, "id", None),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"GMP record {record_id} not found")
    return updated


# ── Application logs for a record ─────────────────────────────────────────────
@router.get("/{record_id}/logs", response_model=List[GMPApplicationLogResponse])
def get_logs(
    record_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    skip = (page - 1) * page_size
    logs, _ = get_gmp_logs(db=db, gmp_id=record_id, skip=skip, limit=page_size)
    return logs


# ── Assign evaluator ──────────────────────────────────────────────────────────
@router.post("/{record_id}/assign", response_model=GMPRecordResponse)
def assign_evaluator(
    record_id: int,
    evaluator_name: str = Query(..., description="Name of evaluator to assign"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    updated = crud.assign_evaluator(
        db, record_id, evaluator_name,
        user_name=getattr(current_user, "username", None),
        user_id=getattr(current_user, "id", None),
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"GMP record {record_id} not found")
    return updated


# ── Advance workflow step ─────────────────────────────────────────────────────
# Routing is entirely table-driven via GMP_ACTION_ROUTES (see
# app/crud/gmp_record.py) — keyed by the exact (current_step, action) pair sent
# from the frontend. This replaces the old positional
# "GMP_LOG_STEPS[current_idx + 1]" logic, which could only ever move forward
# one fixed step at a time and could not express the Evaluator ⇄ Checker loop,
# the Evaluator → QA Admin skip, or any of the "Return to X" backward routes.
@router.post("/{record_id}/advance-step", response_model=GMPApplicationLogResponse)
def advance_step(
    record_id: int,
    req: GMPAdvanceStepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    route_key = (req.current_step, req.action)
    if route_key not in GMP_ACTION_ROUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unrecognized action '{req.action}' from step '{req.current_step}'. "
                "No routing rule exists for this combination in GMP_ACTION_ROUTES — "
                "add one if this is a new, intentional workflow action."
            ),
        )

    next_step_label = GMP_ACTION_ROUTES[route_key]
    next_del_index = GMP_STEP_DEL_INDEX.get(next_step_label) if next_step_label else None

    new_log = gmp_logs.advance_step(
        db, record_id,
        req.current_step, req.action, req.recommendation, req.remarks,
        req.next_assignee_name if next_step_label else None,
        req.next_assignee_id if next_step_label else None,
        next_step_label, next_del_index,
        performed_by_name=getattr(current_user, "username", None),
        performed_by_id=getattr(current_user, "id", None),
        performed_by_alias=getattr(current_user, "alias", None),
        performed_by_full_name=_full_name(current_user),
        action_type=req.action_type,
        decision_result=req.decision_result,
        decision_authority_id=req.decision_authority_id,
        decision_authority_name=req.decision_authority_name,
        doctrack_remarks=req.doctrack_remarks,
        deadline_date=req.deadline_date,
        working_days=req.working_days,
        completion_status=req.completion_status,
    )

    if not new_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No open log found for step '{req.current_step}' on record {record_id}",
        )
    return new_log


# ── Update a specific log (complete with decision details) ────────────────────
@router.patch("/logs/{log_id}", response_model=GMPApplicationLogResponse)
def update_log(
    log_id: int,
    req: GMPApplicationLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # `accomplished_date` is already a real datetime by this point (or None) —
    # GMPApplicationLogUpdate's flexible-date validator normalizes it, instead
    # of the old manual `datetime.fromisoformat` call here that silently kept
    # the raw unparsed string on failure.
    update_data = req.model_dump(exclude_unset=True)
    log = gmp_logs.update_log(db, log_id, update_data)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Log {log_id} not found")
    return log


# ── Reassign ──────────────────────────────────────────────────────────────────
@router.post("/{record_id}/reassign", response_model=GMPApplicationLogResponse)
def reassign_step(
    record_id: int,
    req: GMPReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    new_log = gmp_logs.reassign(
        db,
        gmp_record_id=record_id,
        application_step=req.application_step,
        reassigned_by_user_name=getattr(current_user, "username", None),
        reassigned_by_user_id=getattr(current_user, "id", None),
        reassigned_by_alias=getattr(current_user, "alias", None),
        reassigned_by_full_name=_full_name(current_user),
        reassigned_to_user_name=req.reassigned_to_user_name,
        reassigned_to_user_id=req.reassigned_to_user_id,
        reassignment_reason=req.reassignment_reason,
        reassignment_remarks=req.reassignment_remarks,
    )
    if not new_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No open IN PROGRESS log found for step '{req.application_step}' on record {record_id}",
        )
    return new_log


# ── Reroute ───────────────────────────────────────────────────────────────────
@router.post("/{record_id}/reroute", response_model=GMPApplicationLogResponse)
def reroute_step(
    record_id: int,
    req: GMPRerouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    new_log = gmp_logs.reroute(
        db,
        gmp_record_id=record_id,
        reroute_from_step=req.reroute_from_step,
        reroute_target_step=req.reroute_target_step,
        rerouted_by_user_name=getattr(current_user, "username", None),
        rerouted_by_user_id=getattr(current_user, "id", None),
        rerouted_by_alias=getattr(current_user, "alias", None),
        rerouted_by_full_name=_full_name(current_user),
        target_user_name=req.target_user_name,
        target_user_id=req.target_user_id,
        reroute_reason=req.reroute_reason,
        reroute_remarks=req.reroute_remarks,
    )
    if not new_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No open log found for step '{req.reroute_from_step}' on record {record_id}",
        )
    return new_log


# ── Excel upload ──────────────────────────────────────────────────────────────
@router.post("/upload", summary="Upload filled GMP Excel template")
async def upload_gmp_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    import pandas as pd
    import numpy as np
    from app.api.routes.gmp_upload import (
        GMP_COLUMN_MAPPING, GMP_LOG_STEPS_EXCEL, _parse_date
    )
    from app.models.gmp_record import GMPDelegation, GMPApplicationLogs

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx or .xls files are accepted.",
        )

    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents), sheet_name="Template")
    except Exception:
        try:
            df = pd.read_excel(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not read the Excel file: {str(e)}",
            )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data rows found in the uploaded file.",
        )

    # Normalise all column names to uppercase stripped strings
    df.columns = [str(c).strip().upper() for c in df.columns]

    username  = getattr(current_user, "username", "uploader")
    inserted  = 0
    skipped   = 0
    errors    = []

    for index, row in df.iterrows():
        # Skip completely blank rows
        if all(pd.isna(v) or str(v).strip() == "" for v in row.values):
            continue

        try:
            # ── Core GMPRecord fields ─────────────────────────────────────────
            from app.api.routes.gmp_upload import _parse_date as _parse_upload_date

            DATE_DB_COLUMNS = {
                "GMP_DATE_RECEIVED", "GMP_RELEASED_DATE", "GMP_END_DATE",
                "GMP_NOD_DATE_1", "GMP_NOD_DATE_2", "GMP_NOD_DATE_3",
                "GMP_NOD_DATE_4", "GMP_NOD_DATE_5",
                "GMP_DATE_PRINTED", "GMP_COMPLIANCE_DOCS_DATE_RECEIVED",
            }

            record_data = {}
            for excel_col, db_col in GMP_COLUMN_MAPPING.items():
                raw = row.get(excel_col.upper())

                if db_col in DATE_DB_COLUMNS:
                    parsed = _parse_upload_date(raw)
                    record_data[db_col] = parsed.date() if parsed else None
                    continue

                if pd.isna(raw) or raw is None:
                    record_data[db_col] = None
                elif isinstance(raw, (int, float, np.integer, np.floating)):
                    if db_col == "GMP_DTN":
                        record_data[db_col] = int(raw)
                    else:
                        record_data[db_col] = str(int(raw)) if float(raw) == int(raw) else str(raw)
                else:
                    record_data[db_col] = str(raw).strip() if str(raw).strip() else None

            # Validate / deduplicate DTN
            dtn_val = record_data.get("GMP_DTN")
            if dtn_val is not None:
                if db.query(GMPRecord).filter(GMPRecord.GMP_DTN == dtn_val).first():
                    errors.append({
                        "row_number": index + 2,
                        "dtn": str(dtn_val),
                        "reason": f"DTN {dtn_val} already exists — skipped.",
                    })
                    skipped += 1
                    continue
                # The DTN-dedup check above guarantees this is the first (and
                # only) record for this DTN, so it's always the primary
                # issuance — assign "-01" the same way add_gmp_issuance's
                # _next_reference_no does for later siblings. Without this,
                # GMP_REFERENCE_NO stays NULL forever, and adding an issuance
                # later would assign the SIBLING "-01" while this record (the
                # one actually holding the workflow) stays NULL — both count
                # as "primary" in _primary_only(), producing duplicate rows
                # per DTN in the Queue's Main view.
                record_data["GMP_REFERENCE_NO"] = f"{dtn_val}-01"

            record_data["GMP_USER_UPLOADER"]    = username
            record_data["GMP_DATE_EXCEL_UPLOAD"] = crud._now()

            db_record = GMPRecord(**record_data)
            db.add(db_record)
            db.flush()  # get GMP_ID

            # ── Delegation + ApplicationLogs ──────────────────────────────────
            delegation_kwargs = {}
            DELEGATION_FIELD_MAP = {
                "Decking":      ("GMP_DECKER_1",  "GMP_DECKER_1_DECISION",  "GMP_DECKER_1_REMARKS",  "GMP_DATE_DECKER_1_END"),
                "Evaluator":    ("GMP_EVALUATOR",  "GMP_EVALUATOR_DECISION",  "GMP_EVALUATOR_REMARKS",  "GMP_DATE_EVALUATOR_END"),
                "Checker":      ("GMP_CHECKER",    "GMP_CHECKER_DECISION",    "GMP_CHECKER_REMARKS",    "GMP_DATE_CHECKER_END"),
                "QA Admin":     ("GMP_QA_ADMIN",   "GMP_QA_ADMIN_DECISION",   "GMP_QA_ADMIN_REMARKS",   "GMP_DATE_QA_ADMIN_END"),
                "OD Receiving": ("GMP_OD_RECEIVING", "GMP_OD_RECEIVING_DECISION", "GMP_OD_RECEIVING_REMARKS", "GMP_DATE_OD_RECEIVING_END"),
                "OD Releasing": ("GMP_OD_RELEASING", "GMP_OD_RELEASING_DECISION", "GMP_OD_RELEASING_REMARKS", "GMP_DATE_OD_RELEASING_END"),
            }
            # Keys here now match both GMP_LOG_STEPS_EXCEL's step_label values
            # (app/api/routes/gmp_upload.py) AND GMPDelegation's column names
            # (app/models/gmp_record.py) — "Quality Evaluator"/"QA Supervisor"/
            # the "Decker" 2nd-pass label no longer exist anywhere in this chain.

            logs_inserted = 0
            for (step_label, user_col, id_col, dec_col, rem_col, date_col, thread_col, del_idx) in GMP_LOG_STEPS_EXCEL:
                user_val = row.get(user_col.upper())
                if pd.isna(user_val) or user_val is None or str(user_val).strip() == "":
                    continue

                # Parse user_id
                raw_id = row.get(id_col.upper())
                user_id_val = None
                if raw_id is not None and not (isinstance(raw_id, float) and pd.isna(raw_id)):
                    try:
                        user_id_val = int(float(str(raw_id).strip()))
                    except (ValueError, TypeError):
                        user_id_val = None

                accomplished = _parse_date(row.get(date_col.upper()))
                thread_raw   = row.get(thread_col.upper())
                thread_str   = str(thread_raw).strip() if not pd.isna(thread_raw) and thread_raw else "Open"

                has_date = accomplished is not None
                if thread_str.upper() == "CLOSE" or has_date:
                    thread_str     = "Close"
                    del_last_index = 0
                    log_status     = "COMPLETED"
                else:
                    thread_str     = "Open"
                    del_last_index = 1
                    log_status     = "IN PROGRESS"

                dec_raw = row.get(dec_col.upper())
                rem_raw = row.get(rem_col.upper())
                dec_str = str(dec_raw).strip() if not pd.isna(dec_raw) and dec_raw else ""
                rem_str = str(rem_raw).strip() if not pd.isna(rem_raw) and rem_raw else ""

                log = GMPApplicationLogs(
                    gmp_record_id       = db_record.GMP_ID,
                    application_step    = step_label,
                    user_name           = str(user_val).strip(),
                    user_id             = user_id_val,
                    application_status  = log_status,
                    application_decision= dec_str,
                    application_remarks = rem_str,
                    start_date          = accomplished,
                    accomplished_date   = accomplished,
                    del_index           = del_idx,
                    del_previous        = None,
                    del_last_index      = del_last_index,
                    del_thread          = thread_str,
                    is_received         = 0,
                    is_starred          = 0,
                )
                db.add(log)
                logs_inserted += 1

                # Store delegation fields
                if step_label in DELEGATION_FIELD_MAP:
                    name_f, dec_f, rem_f, date_f = DELEGATION_FIELD_MAP[step_label]
                    delegation_kwargs[name_f] = str(user_val).strip()
                    delegation_kwargs[dec_f]  = dec_str or None
                    delegation_kwargs[rem_f]  = rem_str or None
                    delegation_kwargs[date_f] = accomplished

                # Update GMP_CURRENT_STEP to the last active step
                if log_status == "IN PROGRESS":
                    db_record.GMP_CURRENT_STEP = step_label

            # Create delegation row if any delegation data exists
            if delegation_kwargs:
                delegation = GMPDelegation(
                    GMP_MAIN_ID=db_record.GMP_ID,
                    **delegation_kwargs,
                )
                db.add(delegation)

            db.commit()
            inserted += 1

        except Exception as e:
            db.rollback()
            import traceback
            traceback.print_exc()
            errors.append({
                "row_number": index + 2,
                "dtn": str(row.get("DTN", "-")) if not pd.isna(row.get("DTN", "")) else "-",
                "reason": str(e),
            })

    if inserted == 0 and not errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data rows found in the uploaded file.",
        )

    return {
        "success":  True,
        "inserted": inserted,
        "skipped":  skipped,
        "errors":   errors[:20],
        "message":  f"Upload complete: {inserted} record(s) inserted."
                    + (f" {skipped} skipped." if skipped else ""),
        "stats": {
            "total_processed": inserted + skipped + len(errors),
            "success":  inserted,
            "skipped":  skipped,
            "errors":   len(errors),
        },
    }
