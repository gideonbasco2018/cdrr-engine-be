from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import pandas as pd
import io

from app.core.deps import get_current_active_user
from app.db.deps import DBSessionDep
from app.crud.doctrack import (
    get_document_by_rsn,
    get_document_log_by_id,
    insert_document_log,
    insert_bulk_document_logs,
    get_document_logs_by_ids,
    get_docrecIDs_by_rsns,
    insert_bulk_logs_by_rsns,
)
from app.schemas.doctrack import (
    BulkDocumentLogCreate,
    DocumentLogCreate,
    DocumentLogResponse
)

router = APIRouter(
    prefix="/api/doctrack",
    tags=["FIS - Document Tracking"],
    dependencies=[Depends(get_current_active_user)]
)


# ─────────────────────────────────────────────
# Schemas (for new endpoints only)
# ─────────────────────────────────────────────

class RsnRemarkEntry(BaseModel):
    rsn:     str = Field(..., description="14-digit Doctrack Number")
    remarks: str = Field(..., description="Remarks text")

class BulkByRsnRequest(BaseModel):
    entries: List[RsnRemarkEntry] = Field(..., description="List of RSN + remarks pairs")
    userID:  int                  = Field(..., description="Logged-in user's ID")

class BulkByRsnResponse(BaseModel):
    total_submitted: int
    total_inserted:  int
    total_failed:    int
    inserted:        List[Dict[str, Any]]
    failed:          List[Dict[str, Any]]


# ─────────────────────────────────────────────
# Helpers (for upload-excel)
# ─────────────────────────────────────────────

def _is_valid_rsn(value: str) -> bool:
    """RSN must be exactly 14 numeric digits."""
    return bool(value) and value.isdigit() and len(value) == 14


def _parse_doctrack_excel(contents: bytes) -> pd.DataFrame:
    """
    Parse Excel bytes → DataFrame with columns 'doctrack' and 'remarks'.
    Column detection is case-insensitive partial match:
      - any column containing 'doctrack'  →  'doctrack'
      - any column containing 'remarks'   →  'remarks'
    """
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read Excel file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Excel file is empty.")

    col_map = {}
    for col in df.columns:
        lower = col.strip().lower()
        if "doctrack" in lower and "doctrack" not in col_map:
            col_map["doctrack"] = col
        elif "remarks" in lower and "remarks" not in col_map:
            col_map["remarks"] = col

    if "doctrack" not in col_map:
        raise HTTPException(
            status_code=400,
            detail="Missing required column containing 'doctrack' (e.g. 'Doctrack Number')"
        )
    if "remarks" not in col_map:
        raise HTTPException(
            status_code=400,
            detail="Missing required column containing 'remarks' (e.g. 'Remarks')"
        )

    df = df.rename(columns={col_map["doctrack"]: "doctrack", col_map["remarks"]: "remarks"})
    return df[["doctrack", "remarks"]]


# ─────────────────────────────────────────────
# Existing endpoints (UNCHANGED)
# ─────────────────────────────────────────────

@router.get("/")
def get_document_tracking(
    db: DBSessionDep,
    rsn: str = Query(..., description="Document Tracking Number")
):
    result = get_document_by_rsn(db, rsn)
    if not result:
        raise HTTPException(status_code=404, detail=f"No document found for RSN {rsn}")
    return {"count": len(result), "data": result}


@router.get("/log")
def get_document_log(
    db: DBSessionDep,
    docrecID: str = Query(..., description="Document Receiving Log ID")
):
    result = get_document_log_by_id(db, docrecID)
    if not result:
        raise HTTPException(status_code=404, detail=f"No document log found for docrecID {docrecID}")
    return {"count": len(result), "data": result}


@router.post("/log", response_model=DocumentLogResponse)
def create_document_log(log_data: DocumentLogCreate, db: DBSessionDep):
    inserted_log = insert_document_log(
        db=db,
        docrecID=log_data.docrecID,
        remarks=log_data.remarks,
        userID=log_data.userID
    )
    if not inserted_log:
        raise HTTPException(status_code=500, detail="Failed to create document log")
    return inserted_log


@router.post("/docktrack/log/bulk", response_model=List[DocumentLogResponse])
def create_bulk_document_logs(bulk_data: BulkDocumentLogCreate, db: DBSessionDep):
    inserted_logs = insert_bulk_document_logs(db, [log.dict() for log in bulk_data.logs])
    if not inserted_logs:
        raise HTTPException(status_code=500, detail="Failed to insert document logs")
    return inserted_logs


@router.get("/docktrack/log/bulk", response_model=List[DocumentLogResponse])
def get_bulk_document_logs(
    db: DBSessionDep,
    docrecIDs: List[int] = Query(..., description="List of Document Receiving IDs")
):
    result = get_document_logs_by_ids(db, docrecIDs)
    if not result:
        raise HTTPException(status_code=404, detail=f"No document logs found for docrecIDs {docrecIDs}")
    return result


@router.get("/docktrack/docrecids/bulk", response_model=List[Dict[str, int]])
def get_docrecIDs_bulk(
    db: DBSessionDep,
    rsns: List[str] = Query(..., description="List of RSNs")
):
    result = get_docrecIDs_by_rsns(db, rsns)
    if not result:
        raise HTTPException(status_code=404, detail=f"No docrecIDs found for RSNs {rsns}")
    return result


# ─────────────────────────────────────────────
# NEW: POST /api/doctrack/log/bulk-by-rsn
# JSON endpoint — for programmatic / API callers
# ─────────────────────────────────────────────

@router.post("/log/bulk-by-rsn", response_model=BulkByRsnResponse)
def create_bulk_logs_by_rsn(
    payload: BulkByRsnRequest,
    db: DBSessionDep,
):
    """
    Accepts { entries: [{ rsn, remarks }], userID }.
    Resolves each RSN → docrecID, inserts one log per entry.
    Note: userID is in the request for auth tracking only —
    it is NOT stored (docreceivinglogtbl has no userID column for this operation).
    """
    if not payload.entries:
        raise HTTPException(status_code=400, detail="No entries provided.")

    result = insert_bulk_logs_by_rsns(
        db=db,
        entries=[e.dict() for e in payload.entries],
    )

    return BulkByRsnResponse(
        total_submitted=len(payload.entries),
        total_inserted=len(result["inserted"]),
        total_failed=len(result["failed"]),
        inserted=result["inserted"],
        failed=result["failed"],
    )


# ─────────────────────────────────────────────
# NEW: GET /api/doctrack/download-template
# ─────────────────────────────────────────────

@router.get("/download-template")
async def download_template():
    """
    Download a blank Excel template (.xlsx) with two required columns:
      - Doctrack Number  (must be exactly 14 numeric digits)
      - Remarks          (required, cannot be empty)
    Includes a second sheet with instructions and examples.
    """
    try:
        template_df = pd.DataFrame({
            "Doctrack Number": ["20251114141418"],
            "Remarks":         ["Forwarded to LRD Admin, FAA"],
        })
        instructions_df = pd.DataFrame({
            "Column":      ["Doctrack Number",                                          "Remarks"],
            "Description": ["14-digit Document Tracking Number. Numeric only.",        "Log remarks. Required, cannot be empty."],
            "Example":     ["20251114141418",                                           "Forwarded to LRD Admin, FAA"],
            "Notes":       ["Fully blank rows are skipped automatically.",              "Rows missing Remarks will be skipped and reported as failed."],
        })

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="Upload Template")
            instructions_df.to_excel(writer, index=False, sheet_name="Instructions")
            writer.sheets["Upload Template"].column_dimensions["A"].width = 25
            writer.sheets["Upload Template"].column_dimensions["B"].width = 60
            writer.sheets["Instructions"].column_dimensions["A"].width = 22
            writer.sheets["Instructions"].column_dimensions["B"].width = 55
            writer.sheets["Instructions"].column_dimensions["C"].width = 30
            writer.sheets["Instructions"].column_dimensions["D"].width = 45

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=doctrack_upload_template.xlsx"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")


# ─────────────────────────────────────────────
# NEW: POST /api/doctrack/upload-excel
# Main Excel upload endpoint — called by DoctrackMagicPage
# ─────────────────────────────────────────────

@router.post("/upload-excel")
async def upload_doctrack_excel(
    file:     UploadFile = File(...),
    username: str        = Query(..., description="Logged-in user's username"),
    alias:    str        = Query(default="", description="Uploader's alias"),  # ← IDAGDAG
    db:       DBSessionDep = DBSessionDep,
):
    """
    Upload an Excel file (.xlsx / .xls) with two columns:
      - Doctrack Number  →  looked up as RSN in docreceivingtbl → gets docrecID
      - Remarks          →  stored in docreceivinglogtbl

    INSERT per row:
        docreceivinglogtbl.docrecID  ← from docreceivingtbl WHERE rsn = <Doctrack Number>
        docreceivinglogtbl.logdate   ← NOW()
        docreceivinglogtbl.remarks   ← from Excel row

    Frontend sends:
        POST /api/doctrack/upload-excel?username=JLDLaciapag
        Content-Type: multipart/form-data
        Body: file = <xlsx file>

    Response:
        {
          "success":          true | false,
          "message":          "Upload complete: 12 inserted, 2 failed.",
          "stats":            { "total": 14, "valid": 13, "inserted": 12, "failed": 2 },
          "all_failed":       [ { rowNum, rsn, remarks, reason } ],
          "inserted_records": [ { rowNum, rsn, remarks } ]
        }
    """
    if not file.filename.endswith((".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xls or .xlsx files accepted.")

    contents = await file.read()

    # ── Step 1: Parse Excel ───────────────────────────────────────────────────
    df = _parse_doctrack_excel(contents)

    # ── Step 2: Validate each row ─────────────────────────────────────────────
    valid_entries: List[Dict[str, Any]] = []
    pre_failed:    List[Dict[str, Any]] = []

    for index, row in df.iterrows():
        row_num      = index + 2                            # row 1 = header, index is 0-based
        raw_doctrack = str(row.get("doctrack") or "").strip()
        raw_remarks  = str(row.get("remarks")  or "").strip()

        if not raw_doctrack and not raw_remarks:
            continue                                        # skip fully blank rows silently

        issues = []
        if not raw_doctrack:
            issues.append("Missing Doctrack Number")
        elif not _is_valid_rsn(raw_doctrack):
            issues.append("Invalid format (expected 14 digits)")
        if not raw_remarks:
            issues.append("Missing Remarks")

        if issues:
            pre_failed.append({
                "rowNum":  row_num,
                "rsn":     raw_doctrack,
                "remarks": raw_remarks,
                "reason":  "; ".join(issues),
            })
        else:
            final_remarks = f"{raw_remarks} Remarks by: {alias}" if alias else raw_remarks  # ← IDAGDAG
            valid_entries.append({
                "rowNum":  row_num,
                "rsn":     raw_doctrack,
                "remarks": final_remarks,  
            })

    # Early return — no valid rows at all
    if not valid_entries:
        return {
            "success":          False,
            "message":          "No valid rows to process. All rows have validation errors.",
            "stats":            {"total": len(df), "valid": 0, "inserted": 0, "failed": len(pre_failed)},
            "all_failed":       pre_failed,
            "inserted_records": [],
        }

    # ── Step 3: Lookup docrecIDs + Insert logs ────────────────────────────────
    # insert_bulk_logs_by_rsns: no userID — confirmed no userID column
    bulk_entries = [{"rsn": e["rsn"], "remarks": e["remarks"]} for e in valid_entries]
    result       = insert_bulk_logs_by_rsns(db=db, entries=bulk_entries)

    # Map backend-failed entries back to original rowNum
    backend_failed_rsns   = {f["rsn"] for f in result["failed"]}
    rsn_to_rownum         = {e["rsn"]: e["rowNum"] for e in valid_entries}
    backend_failed_mapped = [
        {
            "rowNum":  rsn_to_rownum.get(f["rsn"], "?"),
            "rsn":     f["rsn"],
            "remarks": f.get("remarks", ""),
            "reason":  f.get("reason", "Unknown error"),
        }
        for f in result["failed"]
    ]

    all_failed        = pre_failed + backend_failed_mapped
    total_inserted    = len(result["inserted"])
    confirmed_entries = [e for e in valid_entries if e["rsn"] not in backend_failed_rsns]

    # ── Step 4: Return result ─────────────────────────────────────────────────
    return {
        "success":          True,
        "message":          f"Upload complete: {total_inserted} inserted, {len(all_failed)} failed.",
        "stats": {
            "total":    len(df),
            "valid":    len(valid_entries),
            "inserted": total_inserted,
            "failed":   len(all_failed),
        },
        "all_failed":       all_failed,           # validation errors + RSN-not-found errors
        "inserted_records": confirmed_entries,    # rows successfully inserted
    }