# app/crud/gmp_dashboard_detail.py
# GMP counterpart of app/crud/dashboard_detail.py.

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date
import math

from app.models.gmp_record import GMPApplicationLogs, GMPRecord
from app.schemas.gmp_dashboard_detail import GMPMetricDetailResponse, GMPApplicationLogDetail


def _base_query(
    db: Session,
    username: str,
    date_from: Optional[date],
    date_to: Optional[date],
):
    q = (
        db.query(GMPApplicationLogs)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .options(joinedload(GMPApplicationLogs.gmp_record))
        .filter(
            GMPApplicationLogs.user_name == username,
            GMPApplicationLogs.del_thread.in_(["Close", "Open"]),
        )
    )
    if date_from:
        q = q.filter(GMPApplicationLogs.start_date >= date_from)
    if date_to:
        q = q.filter(func.date(GMPApplicationLogs.start_date) <= date_to)
    return q


def _apply_metric_filter(q, metric: str):
    if metric == "completed":
        q = q.filter(GMPApplicationLogs.application_status == "COMPLETED")
    elif metric == "on_process":
        q = q.filter(
            GMPApplicationLogs.application_status == "IN PROGRESS",
            GMPApplicationLogs.del_thread == "Open",
        )
    return q


def _row_to_detail(row: GMPApplicationLogs) -> GMPApplicationLogDetail:
    rec = row.gmp_record

    return GMPApplicationLogDetail(
        log_id=row.id,
        gmp_id=rec.GMP_ID if rec else None,
        dtn=str(rec.GMP_DTN) if rec and rec.GMP_DTN is not None else None,
        lto_company=rec.GMP_LTO_COMPANY if rec else None,
        lto_address=rec.GMP_LTO_ADDRESS if rec else None,
        transaction_type=rec.GMP_TRANSACTION_TYPE if rec else None,
        est_category=rec.GMP_EST_CATEGORY if rec else None,
        type_of_issuance=rec.GMP_TYPE_OF_ISSUANCE if rec else None,
        certificate_number=rec.GMP_CERTIFICATE_NUMBER if rec else None,
        secpa_number=rec.GMP_SECPA_NUMBER if rec else None,
        evaluator=rec.GMP_EVALUATOR if rec else None,
        application_status=row.application_status,
        del_thread=row.del_thread,
        app_step=row.application_step,
        start_date=row.start_date,
        end_date=row.accomplished_date,
        user_name=row.user_name,
    )


def get_metric_detail(
    db: Session,
    username: str,
    metric: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    accomplished_date_from: Optional[date] = None,
    accomplished_date_to: Optional[date] = None,
    app_step: Optional[str] = None,
    dtn: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 10,
) -> GMPMetricDetailResponse:
    if metric not in ("received", "completed", "on_process"):
        raise ValueError(
            f"Unknown metric '{metric}'. Use: received | completed | on_process"
        )

    page = max(1, page)
    page_size = max(1, min(500, page_size))

    q = _base_query(db, username, date_from, date_to)
    q = _apply_metric_filter(q, metric)

    if accomplished_date_from:
        q = q.filter(GMPApplicationLogs.accomplished_date >= accomplished_date_from)
    if accomplished_date_to:
        q = q.filter(
            func.date(GMPApplicationLogs.accomplished_date) <= accomplished_date_to
        )

    if app_step:
        q = q.filter(GMPApplicationLogs.application_step == app_step)

    if dtn:
        from sqlalchemy import cast, String

        q = q.filter(cast(GMPRecord.GMP_DTN, String).contains(dtn))

    if sort_by == "dtn":
        order_col = GMPRecord.GMP_DTN
        q = q.order_by(order_col.asc() if sort_dir == "asc" else order_col.desc())
    else:
        q = q.order_by(GMPApplicationLogs.start_date.desc(), GMPApplicationLogs.id.desc())

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))

    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    return GMPMetricDetailResponse(
        metric=metric,
        username=username,
        date_from=date_from,
        date_to=date_to,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=[_row_to_detail(r) for r in rows],
    )
