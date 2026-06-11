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
DOC_TRACK_PATTERN = re.compile(
    r'DOC\s*TRACK\s*[:\-]?\s*[\n\r]?\s*((?:\d[\s]*){14})',
    re.IGNORECASE | re.DOTALL
)
SPACED_DTN_PATTERN = re.compile(r'(?<!\d)((?:\d\s){13}\d)(?!\s*\d)')
BARE_DTN_PATTERN = re.compile(r'(?<!\d)(\d{14})(?!\d)')
OCR_DTN_PATTERN = re.compile(r'[0-9OoIilLSsBZzGgq]{14}', re.IGNORECASE)

# ── Bagong pattern: "Renewal DTN: 2025 0404 110704" (spaced groups) ──
RENEWAL_DTN_PATTERN = re.compile(
    r'Renewal\s+D[TI]N\s*[:\-]?\s*'
    r'([\dOoIilLSsBZzGgq]{6,8}[\s\-]?[\dOoIilLSsBZzGgq]{6,8})',
    re.IGNORECASE
)

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
    # 1. "Doctrack Number" label
    match = DTN_PATTERN.search(text)
    if match:
        return match.group(1)

    # 2. "Renewal DTN:" label — CPR documents
    match = RENEWAL_DTN_PATTERN.search(text)
    if match:
        raw = match.group(1)
        fixed = _fix_sequence(raw)
        # Strip ALL non-digit characters (spaces, dashes, brackets)
        digits_only = re.sub(r'\D', '', fixed)
        if len(digits_only) >= 14:
            return digits_only[:14]
        # If we got fewer digits, try harder — grab next token too
        # (OCR sometimes splits "20250404 110707" across lines)
        extended_match = re.search(
            r'Renewal\s+D[TI]N\s*[:\-]?\s*'
            r'([\dOoIilLSsBZzGgq\s\-\[\]]{14,35})',
            text, re.IGNORECASE
        )
        if extended_match:
            raw2 = _fix_sequence(extended_match.group(1))
            digits2 = re.sub(r'\D', '', raw2)
            if len(digits2) >= 14:
                return digits2[:14]

    # 3. "DOC TRACK" label
    match = DOC_TRACK_PATTERN.search(text)
    if match:
        dtn = re.sub(r'\s+', '', match.group(1))
        if len(dtn) == 14 and dtn.isdigit():
            return dtn

    # 4. Spaced 14-digit pattern
    match = SPACED_DTN_PATTERN.search(text)
    if match:
        dtn = re.sub(r'\s+', '', match.group(1))
        if len(dtn) == 14 and dtn.isdigit():
            return dtn

    # 5. Clean 14-digit number anywhere
    match = BARE_DTN_PATTERN.search(text)
    if match:
        return match.group(1)

    # 6. OCR-corrupted sequences
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


def _extract_text_ocr(pdf_bytes: bytes, max_pages: int = 1) -> str:
    if not PYMUPDF_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(doc)
        # Scan last page muna (barcode usually nasa dulo)
        pages_to_scan = [total - 1] if max_pages == 1 else list(range(min(max_pages, total)))
        for page_num in pages_to_scan:
            page = doc[page_num]
            mat = fitz.Matrix(200 / 72, 200 / 72)  # 200dpi — mas mabilis vs 300
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text += pytesseract.image_to_string(img, lang="eng") + "\n"
        doc.close()
    except Exception as e:
        print(f"[OCR ERROR] {e}")
    return text.strip()


def extract_dtn(pdf_bytes: bytes) -> str | None:
    # Try native first (fast) — but most CPRs are image-based
    text = _extract_text_native(pdf_bytes)
    if text:
        dtn = _find_dtn(text)
        if dtn:
            return dtn

    # OCR — scan last 2 pages (DTN usually nasa page 1 bottom or page 2)
    text_ocr = _extract_text_ocr(pdf_bytes, max_pages=2)
    print(f"[DEBUG] OCR text snippet: {text_ocr[text_ocr.lower().find('renewal'):text_ocr.lower().find('renewal')+100]!r}")
    return _find_dtn(text_ocr)

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

@router.post("/rename-pdfs/debug")
async def debug_pdf(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    
    native_text = _extract_text_native(pdf_bytes)
    ocr_text = _extract_text_ocr(pdf_bytes, max_pages=2)
    
    return {
        "native_text": native_text,
        "ocr_text": ocr_text,
        "native_length": len(native_text),
        "ocr_length": len(ocr_text),
    }