# app/crud/gmp_dashboard_recent.py
# GMP counterpart of app/crud/dashboard_recent.py.
#
# Row field names deliberately match the licensing dashboard's shape
# (dtn / brand_name / generic_name / lto_company / app_step / status_* /
# icon / date_display / log_id) so the existing frontend RecentApplications
# card and modal can render GMP rows without any changes — GMP has no
# "brand name" / "generic name" concept, so those slots are filled with the
# closest GMP equivalents (establishment name, transaction type). `gmp_id`
# is added on top so a row can be resolved back to its GMPRecord.

from sqlalchemy.orm import Session, joinedload
from typing import Optional
import math

from app.models.gmp_record import GMPApplicationLogs, GMPRecord


def get_recent_applications(
    db: Session,
    username: Optional[str] = None,
    limit: int = 10,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    q = (
        db.query(GMPApplicationLogs)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .options(joinedload(GMPApplicationLogs.gmp_record))
    )

    if username is not None:
        q = q.filter(GMPApplicationLogs.user_name == username)

    q = q.order_by(GMPApplicationLogs.created_at.desc())

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))

    rows_orm = q.offset((page - 1) * page_size).limit(page_size).all()

    rows = []
    for log in rows_orm:
        rec = log.gmp_record

        status = (log.application_status or "")
        s = status.upper()

        if s == "COMPLETED":
            status_color = "#36a420"
            status_bg = "#e9f7e6"
            status_label = "Completed"
            icon = "✅"
        elif s == "IN PROGRESS":
            status_color = "#f59e0b"
            status_bg = "#fff8e7"
            status_label = "In Progress"
            icon = "⏳"
        else:
            status_color = "#6b7280"
            status_bg = "#f3f4f6"
            status_label = status or "Unknown"
            icon = "📄"

        rows.append({
            "log_id": log.id,
            "gmp_id": rec.GMP_ID if rec else None,
            "dtn": str(rec.GMP_DTN) if rec and rec.GMP_DTN else "—",
            "brand_name": rec.GMP_LTO_COMPANY if rec else None,
            "generic_name": rec.GMP_TRANSACTION_TYPE if rec else None,
            "lto_company": rec.GMP_LTO_COMPANY if rec else None,
            "app_step": log.application_step,
            "application_status": log.application_status,
            "status_color": status_color,
            "status_bg": status_bg,
            "status_label": status_label,
            "icon": icon,
            "date_display": (
                log.created_at.strftime("%b %d") if log.created_at else "—"
            ),
            "created_at": str(log.created_at) if log.created_at else None,
        })

    return {
        "rows": rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
    }
