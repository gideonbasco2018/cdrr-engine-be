# FILE: app/api/routes/clinical_trials.py
import re
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db  # adjust import to match your DB session dependency
from app.core.deps import (
    get_current_user,
)  # adjust import to match your auth dependency
from app.crud import clinical_trial as crud_clinical_trial
from app.crud import clinical_trial_audit_log as crud_audit_log
from app.schemas.clinical_trial import (
    ClinicalTrialCreate,
    ClinicalTrialUpdate,
    ClinicalTrialOut,
    ClinicalTrialListResponse,
    ClinicalTrialUploadResult,
    ClinicalTrialUploadPreviewRow,
    ClinicalTrialUploadPreviewResult,
)
from app.schemas.clinical_trial_audit_log import ClinicalTrialAuditLogOut
from app.services.clinical_trial_excel import (
    build_template_workbook,
    parse_upload_workbook,
    build_export_workbook,
)

router = APIRouter(prefix="/api/clinical-trials", tags=["Clinical Trials"])


def _friendly_integrity_error(exc: IntegrityError) -> str:
    """
    Turns a raw MySQL duplicate-key error, e.g.
    "Duplicate entry '2012-CT0015' for key 'clinical_trials.ix_clinical_trials_ct_ref_no'",
    into a message that names the actual column instead of the internal
    index name.
    """
    raw_msg = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
    match = re.search(r"Duplicate entry '(.+?)' for key '([^']+)'", raw_msg)
    if not match:
        return raw_msg
    value, key = match.groups()
    field = key.split(".")[-1].replace("ix_clinical_trials_", "").replace("_", " ")
    return f"duplicate {field} '{value}' - a record with this value already exists"


@router.get("/template/download")
def download_template():
    buffer = build_template_workbook()
    filename = "clinical_trial_upload_template.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/download")
def export_clinical_trials(
    search: Optional[str] = None,
    phase: Optional[str] = None,
    drug_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    trials = crud_clinical_trial.get_all_for_export(
        db, search=search, phase=phase, drug_type=drug_type
    )
    buffer = build_export_workbook(trials)
    filename = f"clinical_trials_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/upload", response_model=ClinicalTrialUploadResult)
def upload_clinical_trials(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    file_bytes = file.file.read()
    rows, errors = parse_upload_workbook(file_bytes)

    # Rows are inserted one at a time, each in its own commit. Uploaded
    # trackers commonly carry a stray duplicate (e.g. a repeated CT
    # Reference Number); a single such row should be skipped and reported,
    # not cause the entire batch - including every otherwise-valid row -
    # to roll back.
    inserted = 0
    for row_idx, row in rows:
        try:
            crud_clinical_trial.create(db, row, user_id=current_user.id)
            inserted += 1
        except IntegrityError as exc:
            db.rollback()
            errors.append(f"Row {row_idx}: skipped - {_friendly_integrity_error(exc)}")
        except Exception as exc:
            db.rollback()
            errors.append(f"Row {row_idx}: skipped - {exc}")

    return ClinicalTrialUploadResult(
        total_rows=inserted + len(errors),
        inserted=inserted,
        skipped=len(errors),
        errors=errors,
    )


@router.post("/upload/preview", response_model=ClinicalTrialUploadPreviewResult)
def preview_clinical_trials_upload(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Parses and validates the uploaded workbook the same way the real
    upload does, but never touches the database. Lets the frontend show
    the user what will be inserted and what will fail before they commit
    to the actual upload.
    """
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    file_bytes = file.file.read()
    rows, errors = parse_upload_workbook(file_bytes)

    valid_rows = [
        ClinicalTrialUploadPreviewRow(
            row_number=row_idx,
            protocol_no=row.protocol_no,
            study_title=row.study_title,
            phase=row.phase,
            sponsor_name=row.sponsor_name,
            ct_ref_no=row.ct_ref_no,
            drug_count=len(row.drugs),
        )
        for row_idx, row in rows
    ]

    return ClinicalTrialUploadPreviewResult(
        total_rows=len(valid_rows) + len(errors),
        valid_count=len(valid_rows),
        error_count=len(errors),
        valid_rows=valid_rows,
        errors=errors,
    )


@router.get("", response_model=ClinicalTrialListResponse)
def list_clinical_trials(
    search: Optional[str] = None,
    phase: Optional[str] = None,
    drug_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    rows_per_page: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = crud_clinical_trial.get_list(
        db,
        search=search,
        phase=phase,
        drug_type=drug_type,
        page=page,
        rows_per_page=rows_per_page,
    )
    return ClinicalTrialListResponse(
        total=total, page=page, rows_per_page=rows_per_page, data=rows
    )


@router.post("", response_model=ClinicalTrialOut)
def create_clinical_trial(
    payload: ClinicalTrialCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return crud_clinical_trial.create(db, payload, user_id=current_user.id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=_friendly_integrity_error(exc))


@router.get("/{trial_id}", response_model=ClinicalTrialOut)
def get_clinical_trial(trial_id: int, db: Session = Depends(get_db)):
    trial = crud_clinical_trial.get_by_id(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Clinical trial not found")
    return trial


@router.put("/{trial_id}", response_model=ClinicalTrialOut)
def update_clinical_trial(
    trial_id: int,
    payload: ClinicalTrialUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    trial = crud_clinical_trial.get_by_id(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Clinical trial not found")
    try:
        return crud_clinical_trial.update(db, trial, payload, user_id=current_user.id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=_friendly_integrity_error(exc))


@router.get("/{trial_id}/audit-logs", response_model=List[ClinicalTrialAuditLogOut])
def get_clinical_trial_audit_logs(trial_id: int, db: Session = Depends(get_db)):
    trial = crud_clinical_trial.get_by_id(db, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Clinical trial not found")
    return crud_audit_log.get_logs_for_trial(db, trial_id)
