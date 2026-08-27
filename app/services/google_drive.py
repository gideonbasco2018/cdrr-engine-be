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
_thread_local = threading.local()


def _build_service():
    service = getattr(_thread_local, "service", None)
    if service is None:
        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        _thread_local.service = service
    return service


def folder_exists(folder_id: str) -> bool:
    """I-verify kung buhay pa (hindi na-delete/hindi trashed) ang isang Drive folder ID."""
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
    Hanapin ang file ID kung may existing (hindi pa trashed) na file na
    PAREHONG PANGALAN sa loob ng isang partikular na Drive folder.
    Ginagamit para ma-detect kung dapat i-overwrite/update na lang sa
    halip na gumawa ng duplicate.
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
    Laging gumagawa ng BAGONG file sa Drive (bagong file_id) sa bawat upload —
    tinatanggal ang luma pagkatapos ng successful upload. Ginagawa ito para
    iwasan ang Google Drive thumbnail cache/regeneration delay na nangyayari
    kapag pareho lang ang file_id na ina-overwrite.
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

    # NOTE: no per-file "anyone: reader" permission here anymore — it's an
    # extra Drive round-trip on every single upload. The permission is set
    # once on each folder when it's created (see _find_or_create_child_folder),
    # and Drive permissions are inherited by everything inside.

    # Tanggalin ang lumang file matapos ang successful na bagong upload
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
    folder_id = folder["id"]

    # Make the folder link-viewable once, here — files uploaded into it inherit
    # this, so upload_file_to_drive no longer sets a permission per file.
    try:
        service.permissions().create(
            fileId=folder_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()
    except Exception as exc:
        print(f"[GDrive] failed to set 'anyone' permission on folder {folder_id}: {exc}")

    return folder_id


def get_or_create_application_folder(
    db_entry_type: str,
    db_dtn: str,
    doc_category: Optional[str] = None,
) -> str:
    """
    Gumawa (o hanapin) ng nested folder: ROOT / db_entry_type / db_dtn / [doc_category]
    Returns yung folder_id ng pinaka-loob na folder.

    NOTE: Existing function — HINDI ginalaw ang behavior. Ginawa na lang siyang
    thin wrapper sa ibaba papuntang bagong `get_or_create_folder_path`, pero
    parehas pa rin ang input/output kontrata niya.
    """
    category_parts = [doc_category] if doc_category and doc_category.strip() else []
    return get_or_create_folder_path(db_entry_type, db_dtn, category_parts)


# ── BAGO: generalized version na sumusuporta sa arbitrary-depth na subfolders ──
def get_or_create_folder_path(
    db_entry_type: str,
    db_dtn: str,
    category_parts: Optional[list[str]] = None,
) -> str:
    """
    Gumawa (o hanapin) ng nested folder: ROOT / db_entry_type / db_dtn / cat1 / cat2 / ...
    Suporta na sa multi-level na subfolders (galing sa buong-folder upload,
    kung saan hindi natin alam kung ilang level ang nested subfolders).

    Returns yung folder_id ng pinaka-loob (deepest) na folder.
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
