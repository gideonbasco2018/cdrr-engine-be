# app/services/google_drive.py

import io
import json
import os
import threading
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
