# app/api/routes/softcopy.py
"""Softcopy page routes (/api/softcopy). Softcopies of letters CDRR-OD
receives from FDAC.

The page keeps its letters, sorting and forwards in the user's own browser
(no database). The server only does what a browser can't:

  POST /doctrack      FIS Doctrack for the DTNs the user checked and confirmed
  POST /downloads     log one Excel / PDF file downloaded from the page
  GET  /downloads     the download log (shared), newest first, searchable
  GET  /drive/...     Drive Viewer: list a Drive folder the user pastes and
                      send its files to the browser (read-only, through the
                      system's service account; the folder must be shared
                      with it)

The download log needs the softcopy_downloads table (migration waits for
approval); everything else works without it.

One switch in the backend .env, OFF unless set to "true":
  SOFTCOPY_DOCTRACK_ENABLED  really write to FIS Doctrack (else simulated).
                             FIS is LIVE — switch on only when approved.
"""
import os
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.crud import softcopy as crud
from app.db.session import get_db
from app.models.user import User
from app.services import softcopy_drive as drive
from app.schemas.softcopy import SoftcopyDoctrackRequest, SoftcopyDownloadCreate

router = APIRouter(
    prefix="/api/softcopy",
    tags=["Softcopy"],
    dependencies=[Depends(get_current_active_user)],
)


def doctrack_enabled() -> bool:
    return os.getenv("SOFTCOPY_DOCTRACK_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def _name(user: User) -> str:
    """The user's alias, or their username when no alias is set."""
    return (user.alias or "").strip() or user.username


def _run(fn, *args, **kwargs):
    """crud / Drive errors → HTTP errors with a plain message."""
    try:
        return fn(*args, **kwargs)
    except crud.SoftcopyError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))
    except drive.DriveError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc))


# ── Settings the page needs ──────────────────────────────────────────────────
@router.get("/config")
def get_config():
    """Is the real FIS Doctrack update switched on? (else it's only simulated)"""
    return {"doctrack_enabled": doctrack_enabled()}


# ── FIS Doctrack ─────────────────────────────────────────────────────────────
@router.post("/doctrack")
def doctrack(payload: SoftcopyDoctrackRequest, user: User = Depends(get_current_active_user)):
    """FIS Doctrack for the DTNs the user checked and confirmed."""
    return _run(crud.update_doctrack, payload.dtns, payload.remark, _fis_update(user))


def _fis_update(user: User):
    """FIS Doctrack writer, or None while it's switched off (simulated)."""
    if not doctrack_enabled():
        return None

    def run(dtns: List[str], remark: str) -> dict:
        from app.crud.doctrack import insert_bulk_logs_by_rsns_with_user
        from app.db.remote_session import RemoteSessionLocal

        alias = (user.alias or "").strip()
        text = f"{remark} Remarks by: {alias}" if alias else remark
        entries = [{"rsn": d, "remarks": text, "userID": user.id} for d in dtns]
        fis = RemoteSessionLocal()
        try:
            res = insert_bulk_logs_by_rsns_with_user(db=fis, entries=entries)
        finally:
            fis.close()
        failed = [{"rsn": f.get("rsn"), "reason": f.get("reason", "Failed")} for f in res.get("failed", [])]
        return {"inserted": len(res.get("inserted", [])), "failed": failed}

    return run


# ── Download log ─────────────────────────────────────────────────────────────
@router.post("/downloads")
def log_download(payload: SoftcopyDownloadCreate, db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    return _run(crud.log_download, db, payload, _name(user), user.id)


@router.get("/downloads")
def list_downloads(
    q: str = Query("", max_length=200),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return crud.list_downloads(db, q, limit)


# ── Drive Viewer (read-only) ─────────────────────────────────────────────────
@router.get("/drive/account")
def drive_account():
    """The email folders must be shared with (null = no key on this server)."""
    return {"email": drive.account_email()}


@router.get("/drive/list")
def drive_list(link: str = Query(..., max_length=500), folder_id: Optional[str] = Query(None, max_length=100)):
    """Files in the linked Drive folder (or one of its subfolders)."""
    return _run(drive.list_link, link, folder_id)


@router.get("/drive/file")
def drive_file(root: str = Query(..., max_length=100), file_id: str = Query(..., max_length=100)):
    """One file's bytes, for the viewer to show (inline, not saved)."""
    content, mime, name = _run(drive.read_file, root, file_id)
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(name)}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
