# app/services/google_drive.py

import io
import json
import os
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_credentials() -> service_account.Credentials:
    info_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
    if info_str:
        info = json.loads(info_str)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_path:
        return service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)

    raise RuntimeError(
        "Google Drive credentials not configured. "
        "Set GOOGLE_SERVICE_ACCOUNT_INFO or GOOGLE_SERVICE_ACCOUNT_JSON in .env"
    )


def _build_service():
    creds = _get_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_file_to_drive(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: Optional[str] = None,
) -> dict:
    service   = _build_service()
    folder_id = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    metadata: dict = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)

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

    service.permissions().create(
        fileId=created["id"],
        body={"role": "reader", "type": "anyone"},
        supportsAllDrives=True,
    ).execute()

    return {
        "file_id":   created["id"],
        "file_url":  created.get("webViewLink", ""),
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