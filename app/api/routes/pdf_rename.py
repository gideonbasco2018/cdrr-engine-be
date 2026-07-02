import base64
import io
import json
import re
import zipfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
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

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False


router = APIRouter(prefix="/api", tags=["pdf-rename"])
executor = ThreadPoolExecutor(max_workers=4)

DTN_PATTERN = re.compile(r'Doctrack\s+Number[^\d]*(\d{14})', re.IGNORECASE | re.DOTALL)
DOC_TRACK_PATTERN = re.compile(
    r'DOC\s*TRACK\s*[:\-]?\s*[\n\r]?\s*((?:\d[\s]*){14})',
    re.IGNORECASE | re.DOTALL
)
SPACED_DTN_PATTERN = re.compile(r'(?<!\d)((?:\d\s){13}\d)(?!\s*\d)')
OCR_DTN_PATTERN = re.compile(r'[0-9OoIilLSsBZzGgq]{14}', re.IGNORECASE)
RENEWAL_DTN_PATTERN = re.compile(
    r'Renewal\s+D[TI]N\s*[:\-]?\s*'
    r'([\dOoIilLSsBZzGgq]{6,8}[\s\-]?[\dOoIilLSsBZzGgq]{6,8})',
    re.IGNORECASE
)
# NEW: REG STATUS inline DTN pattern (e.g. "REG. STATUS : Initial (OTC) 20250411083617")
REG_STATUS_DTN_PATTERN = re.compile(
    r'REG[.,]?\s*STATUS\s*[:\-,.]?\s*\w[\w\s]*?\s+(\d{14})',
    re.IGNORECASE
)

EXCLUDE_PREFIXES = ['OR NUMBER', 'OR NO', 'O.R.', 'SEQ NUMBER', 'SEQ NO', 'SEQ:', 'SEQ ', 'SEQ#', '#']

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
    # Step 0: REG STATUS inline DTN — extract BEFORE masking
    match = REG_STATUS_DTN_PATTERN.search(text)
    if match:
        return match.group(1)

    # Mask ONLY the value after known non-DTN labels — single line only ([^\n\r]+)
    cleaned = re.sub(
        r'(?i)(OR\s*N(?:UMBER|O\.?)\s*[:\-]\s*)([^\n\r]+)',
        r'\1MASKED', text
    )
    cleaned = re.sub(
        r'(?i)(REG\.?\s*STATUS\s*[:\-]\s*)([^\n\r]+)',
        r'\1MASKED', cleaned
    )
    cleaned = re.sub(
        r'(?i)(AMOUNT\s*[:\-]\s*)([^\n\r]+)',
        r'\1MASKED', cleaned
    )
    cleaned = re.sub(
        r'(?i)(DATE\s*[:\-]\s*)([^\n\r]+)',
        r'\1MASKED', cleaned
    )

    # 1. "Doctrack Number" label
    match = DTN_PATTERN.search(cleaned)
    if match:
        return match.group(1)

    # 2. "Renewal DTN:" label
    match = RENEWAL_DTN_PATTERN.search(cleaned)
    if match:
        raw = match.group(1)
        fixed = _fix_sequence(raw)
        digits_only = re.sub(r'\D', '', fixed)
        if len(digits_only) >= 14:
            return digits_only[:14]
        extended = re.search(
            r'Renewal\s+D[TI]N\s*[:\-]?\s*([\dOoIilLSsBZzGgq\s\-\[\]]{14,35})',
            cleaned, re.IGNORECASE
        )
        if extended:
            raw2 = _fix_sequence(extended.group(1))
            digits2 = re.sub(r'\D', '', raw2)
            if len(digits2) >= 14:
                return digits2[:14]

    # 3. "DOC TRACK" label
    match = DOC_TRACK_PATTERN.search(cleaned)
    if match:
        dtn = re.sub(r'\s+', '', match.group(1))
        if len(dtn) == 14 and dtn.isdigit():
            return dtn

    # 4. Spaced 14-digit
    match = SPACED_DTN_PATTERN.search(cleaned)
    if match:
        dtn = re.sub(r'\s+', '', match.group(1))
        if len(dtn) == 14 and dtn.isdigit():
            return dtn

    # 5. Standalone 14-digit on its own line — barcode number
    for line in cleaned.split('\n'):
        stripped = line.strip()
        if re.fullmatch(r'\d{14}', stripped):
            return stripped

    # 6. Bare 14-digit — skip known label prefixes
    for match in re.finditer(r'(?<!\d)(\d{14})(?!\d)', cleaned):
        start = match.start()
        prefix = cleaned[max(0, start - 35):start].upper()
        if any(kw in prefix for kw in EXCLUDE_PREFIXES):
            continue
        return match.group(1)

    # 7. OCR-corrupted sequences
    for match in OCR_DTN_PATTERN.finditer(cleaned):
        fixed = _fix_sequence(match.group(0))
        if fixed.isdigit() and len(fixed) == 14:
            return fixed

    return None


def _extract_barcode_area(page) -> str:
    """Native text extraction from right side of page (for text-based PDFs)."""
    try:
        width = float(page.width)
        height = float(page.height)
        bbox = (width * 0.5, height * 0.55, width, height)
        cropped = page.crop(bbox)
        return cropped.extract_text() or ""
    except Exception:
        return ""


def _decode_barcode_pyzbar(fitz_doc, page_num: int) -> str | None:
    """Decode barcode image directly using pyzbar — most accurate for barcode DTN."""
    if not PYZBAR_AVAILABLE or not PYMUPDF_AVAILABLE:
        return None
    try:
        page = fitz_doc[page_num]
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        barcodes = pyzbar_decode(img)
        for barcode in barcodes:
            data = barcode.data.decode("utf-8").strip()
            digits = re.sub(r'\D', '', data)
            if len(digits) == 14:
                return digits
    except Exception as e:
        print(f"[PYZBAR ERROR] page {page_num}: {e}")
    return None


def _ocr_barcode_area(fitz_doc, page_num: int) -> str:
    """OCR right side of page at 300dpi — multiple crop zones."""
    if not PYMUPDF_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""
    try:
        page = fitz_doc[page_num]
        rect = page.rect

        crop_zones = [
            fitz.Rect(rect.width * 0.6, rect.height * 0.4, rect.width, rect.height * 0.7),
            fitz.Rect(rect.width * 0.6, 0, rect.width, rect.height),
            fitz.Rect(rect.width * 0.5, 0, rect.width, rect.height),
        ]

        for clip in crop_zones:
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, clip=clip)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang="eng")
            for line in text.split('\n'):
                stripped = line.strip()
                fixed = _fix_sequence(stripped)
                if re.fullmatch(r'\d{14}', fixed):
                    return text

        # Last resort — full page at 300dpi
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return pytesseract.image_to_string(img, lang="eng")

    except Exception as e:
        print(f"[BARCODE OCR ERROR] page {page_num}: {e}")
        return ""


def extract_dtn(pdf_bytes: bytes) -> str | None:
    """
    Extraction order per page:
    1. Native text — barcode area crop (instant, text-based PDFs)
    2. Full page native text with label patterns
    3. pyzbar barcode decode (direct, most accurate for image-based PDFs)
    4. OCR barcode area at 300dpi (right side only)
    5. Full page OCR at 150dpi (last fallback)
    """
    try:
        plumber_pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
        fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf") if PYMUPDF_AVAILABLE else None
        total = len(plumber_pdf.pages)
        pages_to_check = range(min(3, total))

        for page_num in pages_to_check:
            page = plumber_pdf.pages[page_num]

            # Step 1: Native text barcode area
            barcode_text = _extract_barcode_area(page)
            for line in barcode_text.split('\n'):
                stripped = line.strip()
                if re.fullmatch(r'\d{14}', stripped):
                    plumber_pdf.close()
                    if fitz_doc:
                        fitz_doc.close()
                    return stripped

            # Step 2: Full page native text
            try:
                native = page.extract_text() or ""
            except Exception:
                native = ""

            if native.strip():
                dtn = _find_dtn(native)
                if dtn:
                    plumber_pdf.close()
                    if fitz_doc:
                        fitz_doc.close()
                    return dtn

            # Step 3: pyzbar direct barcode decode
            if fitz_doc:
                dtn = _decode_barcode_pyzbar(fitz_doc, page_num)
                if dtn:
                    plumber_pdf.close()
                    fitz_doc.close()
                    return dtn

            # Step 4: OCR barcode area — try all pages at 300dpi
            if fitz_doc and TESSERACT_AVAILABLE:
                for try_page in range(total):
                    barcode_ocr = _ocr_barcode_area(fitz_doc, try_page)
                    # 4a: standalone 14-digit line
                    for line in barcode_ocr.split('\n'):
                        stripped = line.strip()
                        fixed = _fix_sequence(stripped)
                        if re.fullmatch(r'\d{14}', fixed):
                            plumber_pdf.close()
                            fitz_doc.close()
                            return fixed
                    # 4b: run full _find_dtn on barcode OCR text (catches REG STATUS inline DTN)
                    dtn = _find_dtn(barcode_ocr)
                    if dtn:
                        plumber_pdf.close()
                        fitz_doc.close()
                        return dtn

            # Step 5: Full page OCR at 150dpi
            if fitz_doc and TESSERACT_AVAILABLE:
                try:
                    fitz_page = fitz_doc[page_num]
                    mat = fitz.Matrix(150 / 72, 150 / 72)
                    pix = fitz_page.get_pixmap(matrix=mat)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img, lang="eng")
                    dtn = _find_dtn(ocr_text)
                    if dtn:
                        plumber_pdf.close()
                        fitz_doc.close()
                        return dtn
                except Exception as e:
                    print(f"[OCR ERROR] page {page_num}: {e}")

        plumber_pdf.close()
        if fitz_doc:
            fitz_doc.close()

    except Exception as e:
        print(f"[extract_dtn ERROR] {e}")

    return None


def _process_one(args: tuple) -> dict:
    original_name, pdf_bytes = args
    dtn = extract_dtn(pdf_bytes)
    return {
        "original": original_name,
        "renamed": f"{dtn}.pdf" if dtn else original_name,
        "dtn": dtn,
        "status": "renamed" if dtn else "dtn_not_found",
    }

@router.post("/rename-pdfs/preview")
async def rename_pdfs_preview(files: List[UploadFile] = File(...)):
    """
    Preview DTN extraction results for a batch of PDFs without renaming
    or zipping them. Useful for the frontend to show a confirmation
    table (original name, detected DTN, status) before committing to
    the actual rename/download.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    file_data = [(f.filename or "unknown.pdf", await f.read()) for f in files]

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor,
        lambda: list(map(_process_one, file_data))
    )

    return {
        "results": results,
        "total": len(results),
        "ocr_available": PYMUPDF_AVAILABLE and TESSERACT_AVAILABLE,
        "pyzbar_available": PYZBAR_AVAILABLE,
    }


@router.post("/rename-pdfs")
async def rename_pdfs(files: List[UploadFile] = File(...)):
    """
    Extract the DTN from each uploaded PDF and return them all as a
    single ZIP file, with each PDF renamed to `{dtn}.pdf` (or left
    with its original name if no DTN could be detected). A base64
    JSON summary of per-file results is also returned in the
    X-Rename-Summary response header.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    file_data = [(f.filename or "unknown.pdf", await f.read()) for f in files]

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor,
        lambda: list(map(_process_one, file_data))
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for result, (original_name, pdf_bytes) in zip(results, file_data):
            zf.writestr(result["renamed"], pdf_bytes)

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


@router.post("/rename-pdfs/debug")
async def debug_pdf(file: UploadFile = File(...)):
    """
    Diagnostic endpoint for a single PDF. Runs every extraction stage
    (native text, barcode area crop, pyzbar decode, barcode-area OCR,
    full-page OCR) independently and returns all intermediate outputs
    plus the final detected DTN, so extraction issues can be traced
    stage by stage.
    """
    pdf_bytes = await file.read()
    native_text = ""
    barcode_area_text = ""
    barcode_ocr_text = ""
    pyzbar_results = []
    ocr_text = ""

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, p in enumerate(pdf.pages[:3]):
                native_text += f"[Page {i+1}]\n" + (p.extract_text() or "") + "\n"
                barcode_area_text += f"[Page {i+1} Barcode Area]\n" + _extract_barcode_area(p) + "\n"
    except Exception as e:
        native_text = f"ERROR: {e}"

    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for i in range(min(3, len(doc))):
                dtn_pyzbar = _decode_barcode_pyzbar(doc, i)
                pyzbar_results.append({"page": i + 1, "dtn": dtn_pyzbar})

                barcode_ocr_text += f"[Page {i+1} Barcode OCR]\n" + _ocr_barcode_area(doc, i) + "\n"

                if TESSERACT_AVAILABLE:
                    mat = fitz.Matrix(150 / 72, 150 / 72)
                    pix = doc[i].get_pixmap(matrix=mat)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text += f"[Page {i+1}]\n" + pytesseract.image_to_string(img, lang="eng") + "\n"
            doc.close()
        except Exception as e:
            ocr_text = f"OCR ERROR: {e}"

    return {
        "native_text": native_text.strip(),
        "barcode_area_text": barcode_area_text.strip(),
        "barcode_ocr_text": barcode_ocr_text.strip(),
        "pyzbar_results": pyzbar_results,
        "ocr_text": ocr_text.strip(),
        "detected_dtn": extract_dtn(pdf_bytes),
        "pyzbar_available": PYZBAR_AVAILABLE,
        "ocr_available": PYMUPDF_AVAILABLE and TESSERACT_AVAILABLE,
    }