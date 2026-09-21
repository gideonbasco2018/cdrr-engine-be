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


def _date_ymd(v) -> str:
    """'YYYY-MM-DD...' -> 'YYYY-MM-DD'."""
    return str(v)[:10] if v else ""


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
        ws.append(
            [
                _clean(r.get("dtn")),  # str -> text cell, plain
                _clean(r.get("user_name")),
                _clean(r.get("full_name")),
                _clean(r.get("drug_name")),
                _date_ymd(r.get("date_received_cent")),  # 2026-01-29
                _clean(r.get("entry_type")),
                _clean(r.get("app_step")),
                _clean(r.get("timeline")),
                _clean(r.get("app_status")),
            ]
        )

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out
