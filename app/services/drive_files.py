import io
import re
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account

from app.core.config import settings  # ADAPT

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps."


def _drive():
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES  # ADAPT
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def extract_folder_id(link: str | None) -> str | None:
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", link or "") or re.search(
        r"[?&]id=([A-Za-z0-9_-]+)", link or ""
    )
    return m.group(1) if m else None


def is_inside(drive, root_id: str, item_id: str, max_depth: int = 8) -> bool:
    """Security: the file/folder must live under the application's root folder."""
    current = item_id
    for _ in range(max_depth):
        if current == root_id:
            return True
        meta = (
            drive.files()
            .get(fileId=current, fields="parents", supportsAllDrives=True)
            .execute()
        )
        parents = meta.get("parents") or []
        if not parents:
            return False
        current = parents[0]
    return False


def list_folder(root_id: str, folder_id: str | None = None) -> list[dict]:
    drive = _drive()
    target = folder_id or root_id
    if not is_inside(drive, root_id, target):
        raise PermissionError("Folder is not part of this application")
    res = (
        drive.files()
        .list(
            q=f"'{target}' in parents and trashed=false",
            fields="files(id,name,mimeType,size,modifiedTime)",
            orderBy="folder,name",
            pageSize=200,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return [
        {
            "id": f["id"],
            "name": f["name"],
            "mime_type": f["mimeType"],
            "is_folder": f["mimeType"] == FOLDER_MIME,
            "size": int(f["size"]) if f.get("size") else None,
            "modified_at": f.get("modifiedTime"),
        }
        for f in res.get("files", [])
    ]


def get_file_bytes(root_id: str, file_id: str) -> tuple[bytes, str, str]:
    drive = _drive()
    if not is_inside(drive, root_id, file_id):
        raise PermissionError("File is not part of this application")
    meta = (
        drive.files()
        .get(fileId=file_id, fields="name,mimeType", supportsAllDrives=True)
        .execute()
    )
    mime, name = meta["mimeType"], meta["name"]

    if mime.startswith(GOOGLE_NATIVE_PREFIX):  # Docs/Sheets/Slides -> export as PDF
        request = drive.files().export_media(fileId=file_id, mimeType="application/pdf")
        mime, name = "application/pdf", f"{name}.pdf"
    else:
        request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue(), mime, name
