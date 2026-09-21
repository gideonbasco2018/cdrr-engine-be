from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# (header, width)
COLUMNS = [
    ("DTN", 18),
    ("Username", 16),
    ("Full Name", 26),
    ("Drug / Application", 60),
    ("Date Received", 14),
    ("Entry Type", 14),
    ("Step", 22),
    ("Timeline", 12),
    ("Status", 14),
]


def _clean(v) -> str:
    """Tanggal ang line breaks, extra spaces, at leading/trailing whitespace."""
    return " ".join(str(v).split()) if v is not None else ""


def _to_int(v):
    """DTN -> real number. Kapag hindi ma-convert, ibabalik ang original text."""
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return _clean(v)


def _to_date(v):
    """'YYYY-MM-DD...' -> real date object. Kapag hindi ma-parse, ibabalik ang original text."""
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return _clean(v)


def build_records_xlsx(rows: list[dict]) -> BytesIO:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Records")

    for i, (_, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"

    header_fill = PatternFill(
        start_color="1F4E79", end_color="1F4E79", fill_type="solid"
    )
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_align = Alignment(horizontal="center", vertical="center")

    header_cells = []
    for name, _ in COLUMNS:
        c = WriteOnlyCell(ws, value=name)
        c.fill, c.font, c.alignment = header_fill, header_font, header_align
        header_cells.append(c)
    ws.append(header_cells)

    for r in rows:
        # DTN: real number, format "0" (walang E+13, walang green triangle)
        dtn_cell = WriteOnlyCell(ws, value=_to_int(r.get("dtn")))
        dtn_cell.number_format = "0"
        dtn_cell.alignment = Alignment(horizontal="left")

        # Real Excel date, naka-format na yyyy-mm-dd
        date_cell = WriteOnlyCell(ws, value=_to_date(r.get("date_received_cent")))
        date_cell.number_format = "yyyy-mm-dd"

        ws.append(
            [
                dtn_cell,  # str -> text cell, plain
                _clean(r.get("user_name")),
                _clean(r.get("full_name")),
                _clean(r.get("drug_name")),
                date_cell,  # 2026-01-29 (real date)
                _clean(r.get("entry_type")),
                _clean(r.get("app_step")),
                _clean(r.get("timeline")),
                _clean(r.get("app_status")),
            ]
        )
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out
