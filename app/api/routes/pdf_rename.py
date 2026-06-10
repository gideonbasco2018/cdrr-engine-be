import base64
import io
import json
import re
import zipfile
from typing import List

import pdfplumber
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


router = APIRouter(prefix="/api", tags=["pdf-rename"])

DTN_PATTERN = re.compile(r'Doctrack\s+Number[^\d]*(\d{14})', re.IGNORECASE | re.DOTALL)
BARE_DTN_PATTERN = re.compile(r'(?<!\d)(\d{14})(?!\d)')
# Match OCR-corrupted 14-char sequences (digits + common misreads)
OCR_DTN_PATTERN = re.compile(r'[0-9OoIilLSsBZzGgq]{14}', re.IGNORECASE)

OCR_FIXES = {
    'O': '0', 'o': '0',
    'I': '1', 'i': '1', 'l': '1', 'L': '1',
    'S': '5', 's': '5',
    'B': '8',
    'Z': '2', 'z': '2',
    'G': '6', 'g': '9', 'q': '9',
}

def _fix_sequence(seq: str) -> str:
    return ''.join(OCR_FIXES.get(c, c) for c in seq)


def _find_dtn(text: str) -> str | None:
    # 1. Try clean DTN after "Doctrack Number" label
    match = DTN_PATTERN.search(text)
    if match:
        return match.group(1)

    # 2. Try clean 14-digit number anywhere
    match = BARE_DTN_PATTERN.search(text)
    if match:
        return match.group(1)

    # 3. Try OCR-corrupted sequences — fix then validate
    for match in OCR_DTN_PATTERN.finditer(text):
        fixed = _fix_sequence(match.group(0))
        if fixed.isdigit() and len(fixed) == 14:
            return fixed

    return None


def _extract_text_native(pdf_bytes: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    return text.strip()


def _extract_text_ocr(pdf_bytes: bytes, max_pages: int = 2) -> str:
    if not PYMUPDF_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_to_scan = min(max_pages, len(doc))
        for page_num in range(pages_to_scan):
            page = doc[page_num]
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img, lang="eng") + "\n"
        doc.close()
    except Exception:
        pass
    return text.strip()


def extract_dtn(pdf_bytes: bytes) -> str | None:
    text = _extract_text_native(pdf_bytes)
    dtn = _find_dtn(text)
    if dtn:
        return dtn
    text = _extract_text_ocr(pdf_bytes)
    return _find_dtn(text)


@router.post("/rename-pdfs")
async def rename_pdfs(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for upload in files:
            original_name = upload.filename or "unknown.pdf"
            pdf_bytes = await upload.read()
            dtn = extract_dtn(pdf_bytes)
            new_name = f"{dtn}.pdf" if dtn else original_name
            status = "renamed" if dtn else "dtn_not_found"
            zf.writestr(new_name, pdf_bytes)
            results.append({"original": original_name, "renamed": new_name, "status": status})

    zip_buffer.seek(0)
    summary_header = base64.b64encode(json.dumps(results).encode()).decode()

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=renamed_pdfs.zip",
            "X-Rename-Summary": summary_header,
        },
    )


@router.post("/rename-pdfs/preview")
async def rename_pdfs_preview(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results = []
    for upload in files:
        original_name = upload.filename or "unknown.pdf"
        pdf_bytes = await upload.read()
        dtn = extract_dtn(pdf_bytes)
        results.append({
            "original": original_name,
            "renamed": f"{dtn}.pdf" if dtn else original_name,
            "dtn": dtn,
            "status": "renamed" if dtn else "dtn_not_found",
        })

    return {
        "results": results,
        "total": len(results),
        "ocr_available": PYMUPDF_AVAILABLE and TESSERACT_AVAILABLE,
    }
