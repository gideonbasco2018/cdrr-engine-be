# app/services/google_drive.py

import io
import json
import os
import threading
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_credentials() -> service_account.Credentials:
    info_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    if info_str:
        info = json.loads(info_str)
        return service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )

    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_path:
        return service_account.Credentials.from_service_account_file(
            json_path, scopes=SCOPES
        )

    raise RuntimeError(
        "Google Drive credentials not configured. "
        "Set GOOGLE_SERVICE_ACCOUNT_INFO or GOOGLE_SERVICE_ACCOUNT_JSON in .env"
    )


# The Drive service object (and its underlying http transport) is not
# thread-safe, but building it on every call is wasteful — a single file
# upload touches Drive ~4 times. Cache one service PER THREAD: sync FastAPI
# endpoints run in a bounded worker pool, so this ends up being a handful of
# reused clients instead of one rebuilt per Drive call.
#
# NOTE: only safe if every caller is a sync `def` endpoint / worker thread
# (FastAPI's threadpool) or a dedicated worker thread (Celery/RQ). If any
# `async def` route calls these functions directly without
# run_in_threadpool/asyncio.to_thread, it runs on the event loop thread and
# could share this cached client across concurrent coroutines unsafely.
_thread_local = threading.local()


def _build_service():
    service = getattr(_thread_local, "service", None)
    if service is None:
        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        _thread_local.service = service
    return service


def folder_exists(folder_id: str) -> bool:
    """Check whether a Drive folder ID is still alive (not deleted / not trashed)."""
    if not folder_id:
        return False
    try:
        service = _build_service()
        meta = (
            service.files()
            .get(fileId=folder_id, fields="id, trashed", supportsAllDrives=True)
            .execute()
        )
        return not meta.get("trashed", False)
    except Exception:
        return False


def find_file_in_folder(filename: str, folder_id: str) -> Optional[str]:
    """
    Find the file ID of an existing (not trashed) file with the SAME NAME
    inside a specific Drive folder. Used to detect whether we should
    overwrite/update instead of creating a duplicate.
    """
    if not folder_id:
        return None
    try:
        service = _build_service()
        safe_name = filename.replace("'", "\\'")
        query = (
            f"name = '{safe_name}' "
            f"and '{folder_id}' in parents "
            f"and trashed = false"
        )
        results = (
            service.files()
            .list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name)",
            )
            .execute()
        )
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception as exc:
        print(f"[GDrive] find_file_in_folder error for '{filename}': {exc}")
        return None


def upload_file_to_drive(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: Optional[str] = None,
    existing_file_id: Optional[str] = None,
) -> dict:
    """
    Always creates a NEW file in Drive (new file_id) on every upload —
    deletes the old one after a successful upload. This avoids the Google
    Drive thumbnail cache/regeneration delay that happens when overwriting
    the same file_id.
    """
    service = _build_service()
    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=mime_type,
        resumable=True,
        chunksize=5 * 1024 * 1024,
    )

    metadata: dict = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    created = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink, parents",
            supportsAllDrives=True,
        )
        .execute()
    )

    # IMPORTANT: kept intentionally, per-file, on EVERY upload. Do not remove
    # in favor of folder-level-only permissions unless a backfill has been run
    # against all pre-existing folders AND _find_or_create_child_folder verifies
    # permission on the existing-folder path too (not just newly-created ones).
    # Without both of those, uploads into any pre-existing folder silently lose
    # public access — no exception is raised, the link is just inaccessible.
    try:
        service.permissions().create(
            fileId=created["id"],
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()
    except Exception as exc:
        print(
            f"[GDrive] failed to set 'anyone' permission on file {created['id']}: {exc}"
        )

    # Delete the old file after the successful new upload
    if existing_file_id:
        try:
            service.files().delete(
                fileId=existing_file_id,
                supportsAllDrives=True,
            ).execute()
        except Exception as exc:
            print(f"[GDrive] failed to delete old file {existing_file_id}: {exc}")

    return {
        "file_id": created["id"],
        "file_url": created.get("webViewLink", ""),
        "folder_id": (created.get("parents") or [None])[0],
    }


def delete_file_from_drive(file_id: str) -> bool:
    try:
        service = _build_service()
        service.files().delete(
            fileId=file_id,
            supportsAllDrives=True,
        ).execute()
        return True
    except Exception as exc:
        print(f"[GDrive] delete_file error for {file_id}: {exc}")
        return False


# Drive roles from least to most access; "fileOrganizer"/"organizer" are the
# Shared Drive roles above writer.
_ROLE_RANK = {"reader": 0, "commenter": 1, "writer": 2, "fileOrganizer": 3, "organizer": 4, "owner": 5}


def grant_user_access(file_id: str, email: str, role: str) -> str:
    """Give `email` at least `role` ("commenter" or "writer") on a file.
    Never lowers access someone already has. Returns the role they end up with.
    Raises on Drive errors so the caller can report them."""
    service = _build_service()
    perms = service.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role,emailAddress)",
        supportsAllDrives=True,
    ).execute().get("permissions", [])
    email_l = email.lower()
    existing = next(
        (p for p in perms if p.get("type") == "user" and (p.get("emailAddress") or "").lower() == email_l),
        None,
    )
    if existing:
        if _ROLE_RANK.get(existing["role"], 0) >= _ROLE_RANK[role]:
            return existing["role"]
        service.permissions().update(
            fileId=file_id, permissionId=existing["id"],
            body={"role": role}, supportsAllDrives=True,
        ).execute()
        return role
    service.permissions().create(
        fileId=file_id,
        body={"type": "user", "role": role, "emailAddress": email},
        sendNotificationEmail=False,
        supportsAllDrives=True,
    ).execute()
    return role


def remove_user_edit_comment_access(file_id: str) -> int:
    """Remove every edit/comment access given to a person directly on this
    file. Leaves "anyone with the link can view" and the Shared Drive's own
    members (inherited access) untouched. Returns how many were removed."""
    service = _build_service()
    perms = service.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role,permissionDetails(inherited))",
        supportsAllDrives=True,
    ).execute().get("permissions", [])
    removed = 0
    for p in perms:
        inherited = any(d.get("inherited") for d in p.get("permissionDetails", []))
        if p.get("type") == "user" and p.get("role") in ("writer", "commenter") and not inherited:
            service.permissions().delete(
                fileId=file_id, permissionId=p["id"], supportsAllDrives=True,
            ).execute()
            removed += 1
    return removed


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
_W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"


def count_docx_open_comments(file_id: str) -> dict:
    """Count open comments inside a .docx stored in Drive.

    Google Docs saves comments on a .docx INTO the file (word/comments.xml),
    not in Drive's comment list, and drops a comment from the file once it is
    resolved. Word keeps resolved ones but marks them done — skipped here.
    Replies are linked to their comment via word/commentsExtended.xml.
    Returns {"comments": <open top-level>, "replies": <replies on them>}."""
    service = _build_service()
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id, supportsAllDrives=True))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    z = zipfile.ZipFile(buf)
    names = set(z.namelist())
    if "word/comments.xml" not in names:
        return {"comments": 0, "replies": 0}

    extended = {}
    if "word/commentsExtended.xml" in names:
        for e in ET.fromstring(z.read("word/commentsExtended.xml")).iter(_W15 + "commentEx"):
            extended[e.get(_W15 + "paraId")] = e

    comments = replies = 0
    for c in ET.fromstring(z.read("word/comments.xml")).iter(_W + "comment"):
        paras = c.findall(".//" + _W + "p")
        ext = extended.get(paras[-1].get(_W14 + "paraId")) if paras else None
        if ext is not None and ext.get(_W15 + "done") == "1":
            continue
        if ext is not None and ext.get(_W15 + "paraIdParent"):
            replies += 1
        else:
            comments += 1
    return {"comments": comments, "replies": replies}


def _find_or_create_child_folder(
    service, parent_id: str, folder_name: str, drive_id: str
) -> str:
    query = (
        f"name = '{folder_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )
    results = (
        service.files()
        .list(
            q=query,
            corpora="drive",
            driveId=drive_id,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields="files(id, name)",
        )
        .execute()
    )

    existing = results.get("files", [])
    if existing:
        return existing[0]["id"]

    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = (
        service.files()
        .create(body=folder_metadata, fields="id", supportsAllDrives=True)
        .execute()
    )
    return folder["id"]


def get_or_create_application_folder(
    db_entry_type: str,
    db_dtn: str,
    doc_category: Optional[str] = None,
) -> str:
    """
    Create (or find) a nested folder: ROOT / db_entry_type / db_dtn / [doc_category]
    Returns the folder_id of the innermost folder.

    NOTE: Existing function — behavior NOT changed. It's now just a thin
    wrapper around the new `get_or_create_folder_path` below, but keeps the
    same input/output contract.
    """
    category_parts = [doc_category] if doc_category and doc_category.strip() else []
    return get_or_create_folder_path(db_entry_type, db_dtn, category_parts)


# ── NEW: generalized version that supports arbitrary-depth subfolders ──
def get_or_create_folder_path(
    db_entry_type: str,
    db_dtn: str,
    category_parts: Optional[list[str]] = None,
) -> str:
    """
    Create (or find) a nested folder: ROOT / db_entry_type / db_dtn / cat1 / cat2 / ...
    Now supports multi-level subfolders (for whole-folder uploads, where we
    don't know how many levels of nested subfolders there are).

    Returns the folder_id of the innermost (deepest) folder.
    """
    service = _build_service()
    root_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not root_folder_id:
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is not configured in .env")

    db_entry_type = (db_entry_type or "Unknown").strip()
    db_dtn = (db_dtn or "Unknown").strip()

    current_id = _find_or_create_child_folder(
        service, root_folder_id, db_entry_type, drive_id=root_folder_id
    )
    current_id = _find_or_create_child_folder(
        service, current_id, db_dtn, drive_id=root_folder_id
    )

    for part in category_parts or []:
        part = (part or "").strip()
        if part:
            current_id = _find_or_create_child_folder(
                service, current_id, part, drive_id=root_folder_id
            )

    return current_id
