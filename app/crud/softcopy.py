# app/crud/softcopy.py
"""Softcopy page: the FIS Doctrack update and the download log.

The letters themselves live in the user's browser, not here. Times are stored
in UTC (the DB runs in UTC) and sent as ISO text ending in "Z" so the browser
shows them in local time."""
import re
from datetime import datetime
from typing import Callable, List, Optional

from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session

from app.models.softcopy import SoftcopyDownload

REMARK_PREFIX = "Softcopy Received by CDRR - OD and forwarded to "
DTN_RE = re.compile(r"^\d{14}$")


class SoftcopyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\t", " ")).strip()


def iso(v) -> Optional[str]:
    if isinstance(v, datetime):
        return v.replace(microsecond=0).isoformat() + "Z"
    return None if v is None else str(v)


def clean_dtns(dtns: List[str]) -> List[str]:
    """Trimmed, no repeats, in order. Every one must be 14 digits."""
    out: List[str] = []
    for d in dtns or []:
        s = clean(d)
        if not DTN_RE.match(s):
            raise SoftcopyError(f'"{s}" is not a 14-digit DTN.')
        if s not in out:
            out.append(s)
    return out


# ── FIS Doctrack (only after the user checked the list and clicked Confirm) ──
def check_remark(remark: str) -> str:
    """The remark must be "Softcopy Received by CDRR - OD and forwarded to <code>"."""
    r = clean(remark)
    if not r.startswith(REMARK_PREFIX) or not r[len(REMARK_PREFIX):].strip():
        raise SoftcopyError("The FIS remark must end with the unit's code.")
    if len(r) > 200:
        raise SoftcopyError("The FIS remark is too long.")
    return r


def update_doctrack(
    dtns: List[str],
    remark: str,
    doctrack: Optional[Callable[[List[str], str], dict]],
) -> dict:
    """Write the remark to FIS Doctrack for the confirmed DTNs.

    doctrack(dtns, remark) → {inserted, failed: [{rsn, reason}]}; None = FIS is
    switched off, so it's only simulated (nothing sent to FIS). The page marks
    the DTNs that worked on its own side; nothing is saved here."""
    remark = check_remark(remark)
    dtns = clean_dtns(dtns)
    if not dtns:
        raise SoftcopyError("No DTNs to update.")
    if doctrack is None:
        return {"inserted": len(dtns), "failed": [], "simulated": True}
    try:
        res = doctrack(dtns, remark)
    except Exception as exc:  # FIS down: every DTN failed
        res = {"inserted": 0, "failed": [{"rsn": d, "reason": f"FIS error: {exc}"} for d in dtns]}
    return {"inserted": res.get("inserted", 0), "failed": res.get("failed", []), "simulated": False}


# ── Download log ─────────────────────────────────────────────────────────────
def download_out(d: SoftcopyDownload) -> dict:
    return {
        "id": d.id,
        "file_name": d.file_name,
        "file_type": d.file_type,
        "kind": d.kind,
        "unit": d.unit,
        "letter_count": d.letter_count,
        "dtns": list(d.dtns or []),
        "downloaded_by": d.downloaded_by,
        "downloaded_at": iso(d.downloaded_at),
    }


def log_download(db: Session, req, by: str, user_id: int) -> dict:
    dtns = clean_dtns(req.dtns)
    if not dtns:
        raise SoftcopyError("The file has no DTNs.")
    row = SoftcopyDownload(
        file_name=clean(req.file_name)[:255],
        file_type=req.file_type,
        kind=req.kind,
        unit=clean(req.unit) or None,
        letter_count=len(dtns),
        dtns=dtns,
        downloaded_by=by,
        downloaded_by_user_id=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return download_out(row)


def list_downloads(db: Session, q: str = "", limit: int = 200) -> List[dict]:
    """Newest first. q = part of a file name, a unit, a name, or a DTN."""
    query = db.query(SoftcopyDownload)
    s = clean(q)
    if s:
        like = f"%{s}%"
        query = query.filter(or_(
            SoftcopyDownload.file_name.ilike(like),
            SoftcopyDownload.unit.ilike(like),
            SoftcopyDownload.downloaded_by.ilike(like),
            # the JSON list read as text, e.g. ["20260805000001", …]
            cast(SoftcopyDownload.dtns, Text).like(like),
        ))
    rows = query.order_by(SoftcopyDownload.id.desc()).limit(max(1, min(limit, 1000))).all()
    return [download_out(d) for d in rows]
