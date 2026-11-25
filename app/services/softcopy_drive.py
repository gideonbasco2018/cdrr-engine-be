# app/services/softcopy_drive.py
"""Read-only Google Drive access for the Softcopy page's Drive Viewer.

The user pastes / drops a Drive folder (or file) link; the viewer lists the
files and opens them in the browser's memory (nothing saved on the user's
computer). Uses the system's service account (same key as
app/services/google_drive.py) but with the READ-ONLY scope.

Rules:
  · Google only lets the service account read folders shared with it
    (Viewer is enough). Otherwise → DriveError 403 with the email to share with.
  · Only items under the link the user gave can be read (parent walk).
  · Never reads the system's own upload Shared Drive (GOOGLE_DRIVE_FOLDER_ID).
"""
import io
import json
import os
import re
import threading
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
NATIVE_PREFIX = "application/vnd.google-apps."
MAX_BYTES = 60 * 1024 * 1024  # bigger files: open them in Drive instead
ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")


class DriveError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _credentials():
    from google.oauth2 import service_account

    info = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    if info:
        return service_account.Credentials.from_service_account_info(json.loads(info), scopes=SCOPES)
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if path and os.path.exists(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    raise DriveError("Drive reading isn't set up on this server (no service account key).", 503)


_local = threading.local()


def _drive():
    svc = getattr(_local, "svc", None)
    if svc is None:
        from googleapiclient.discovery import build

        svc = build("drive", "v3", credentials=_credentials(), cache_discovery=False)
        _local.svc = svc
    return svc


def account_email() -> Optional[str]:
    """The email to share folders with (None when no key)."""
    try:
        return _credentials().service_account_email
    except DriveError:
        return None


def parse_link(link: str) -> str:
    """Drive / Docs link (or a bare id) → the folder or file id."""
    s = (link or "").strip()
    if ID_RE.match(s):
        return s
    m = (
        re.search(r"/folders/([A-Za-z0-9_-]+)", s)
        or re.search(r"/(?:file|document|spreadsheets|presentation)/d/([A-Za-z0-9_-]+)", s)
        or re.search(r"[?&]id=([A-Za-z0-9_-]+)", s)
    )
    if not m or not re.match(r"^https://(drive|docs)\.google\.com/", s):
        raise DriveError("That isn't a Google Drive link.")
    return m.group(1)


def _call(req):
    """Run a Drive request; turn Google's errors into plain messages."""
    from googleapiclient.errors import HttpError

    try:
        return req.execute()
    except HttpError as exc:
        code = getattr(exc.resp, "status", 500)
        if code in (403, 404):
            who = account_email()
            raise DriveError(
                "The system can't open this. Share the folder with "
                f"{who or 'the system account'} as Viewer, then try again.",
                403,
            )
        raise DriveError("Google Drive didn't answer. Try again.", 502)


def _meta(file_id: str) -> dict:
    return _call(
        _drive().files().get(
            fileId=file_id, fields="id,name,mimeType,size,modifiedTime,parents,driveId,trashed",
            supportsAllDrives=True,
        )
    )


def _check_not_system(meta: dict) -> None:
    own = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if own and (meta.get("driveId") == own or meta.get("id") == own):
        raise DriveError("This folder belongs to the system's own uploads and can't be opened here.", 403)


def _inside(root_id: str, item_id: str, max_depth: int = 10) -> bool:
    current = item_id
    for _ in range(max_depth):
        if current == root_id:
            return True
        parents = _meta(current).get("parents") or []
        if not parents:
            return False
        current = parents[0]
    return False


def _item(f: dict) -> dict:
    return {
        "id": f["id"],
        "name": f["name"],
        "mime_type": f["mimeType"],
        "is_folder": f["mimeType"] == FOLDER_MIME,
        "size": int(f["size"]) if f.get("size") else None,
        "modified_at": f.get("modifiedTime"),
    }


def list_link(link: str, folder_id: Optional[str] = None) -> dict:
    """The files in the linked folder (or one of its subfolders).
    A file link → that one file."""
    root_id = parse_link(link)
    root = _meta(root_id)
    _check_not_system(root)
    if root.get("trashed"):
        raise DriveError("That item is in the Drive trash.", 404)

    if root["mimeType"] != FOLDER_MIME:
        return {"root_id": root_id, "root_name": root["name"], "folder_id": None, "path": [], "items": [_item(root)]}

    target = folder_id or root_id
    if not ID_RE.match(target):
        raise DriveError("Bad folder id.")
    path = []
    if target != root_id:
        if not _inside(root_id, target):
            raise DriveError("That folder isn't inside the link you gave.", 403)
        # breadcrumb: root › … › target
        cur = target
        while cur != root_id:
            m = _meta(cur)
            path.insert(0, {"id": m["id"], "name": m["name"]})
            cur = (m.get("parents") or [root_id])[0]

    items, token = [], None
    while True:
        res = _call(
            _drive().files().list(
                q=f"'{target}' in parents and trashed=false",
                fields="nextPageToken,files(id,name,mimeType,size,modifiedTime)",
                orderBy="folder,name",
                pageSize=200,
                pageToken=token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        )
        items += [_item(f) for f in res.get("files", [])]
        token = res.get("nextPageToken")
        if not token or len(items) >= 1000:
            break
    return {"root_id": root_id, "root_name": root["name"], "folder_id": target, "path": path, "items": items}


def read_file(root_id: str, file_id: str) -> tuple:
    """(bytes, mime, name) of a file under root_id. Google Docs/Sheets/Slides
    come back as PDF. Kept in memory only, never saved."""
    from googleapiclient.http import MediaIoBaseDownload

    for v in (root_id, file_id):
        if not ID_RE.match(v or ""):
            raise DriveError("Bad id.")
    root = _meta(root_id)
    _check_not_system(root)
    meta = root if file_id == root_id else _meta(file_id)
    if file_id != root_id and not _inside(root_id, file_id):
        raise DriveError("That file isn't inside the link you gave.", 403)
    if meta["mimeType"] == FOLDER_MIME:
        raise DriveError("That's a folder, not a file.")
    if meta.get("size") and int(meta["size"]) > MAX_BYTES:
        raise DriveError("This file is too big to open here. Use Open in Drive.", 413)

    name, mime = meta["name"], meta["mimeType"]
    if mime.startswith(NATIVE_PREFIX):
        req = _drive().files().export_media(fileId=file_id, mimeType="application/pdf")
        name, mime = f"{name}.pdf", "application/pdf"
    else:
        req = _drive().files().get_media(fileId=file_id, supportsAllDrives=True)

    from googleapiclient.errors import HttpError

    buf = io.BytesIO()
    try:
        dl = MediaIoBaseDownload(buf, req, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
            if buf.tell() > MAX_BYTES:
                raise DriveError("This file is too big to open here. Use Open in Drive.", 413)
    except HttpError:
        raise DriveError("Google Drive couldn't send this file. Try again or use Open in Drive.", 502)
    return buf.getvalue(), mime, name
