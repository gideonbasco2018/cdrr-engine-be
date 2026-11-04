import base64
import html
import json
import logging
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.models.e_app_email_notification import EAppEmailNotification
from app.models.e_app_email_notification_attempt import EAppEmailNotificationAttempt
from app.models.e_app_order_of_payment import EAppOrderOfPayment
from app.models.e_app_payment_verification import EAppPaymentVerification

logger = logging.getLogger(__name__)

MANILA = ZoneInfo("Asia/Manila")
BANCNET_FEE = 15.0

DOC_AR = "ACKNOWLEDGEMENT_RECEIPT"
DOC_AOOP = "ADDITIONAL_ORDER_OF_PAYMENT"

# cdrr-engine-be/static/images (ADAPT if your static folder is elsewhere)
LOGO_DIR = Path(__file__).resolve().parents[2] / "static" / "images"


# ───────────────────────── helpers ─────────────────────────
def _logo_img(filename: str, width: str, height: str) -> str:
    try:
        data = base64.b64encode((LOGO_DIR / filename).read_bytes()).decode()
    except OSError:
        logger.warning("Logo not found: %s", LOGO_DIR / filename)
        return ""
    return (
        f'<img src="data:image/png;base64,{data}" '
        f'style="width:{width};height:{height};object-fit:contain;">'
    )


def _php(value) -> str:
    return f"Php {float(value or 0):,.2f}"


def _to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _long_date(value) -> str:
    d = _to_date(value)
    return f"{d:%B} {d.day}, {d.year}" if d else str(value or "")


def _form_data(application) -> dict:
    # ADAPT: attribute name of the form data on EApplication
    data = getattr(application, "form_data", None)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {}
    return data if isinstance(data, dict) else {}


def _general_info(application) -> dict:
    return {
        "reference_number": application.reference_number,
        "activity": application.activity,
        "application_type": application.application_type,
        "classification": _form_data(application).get("Classification"),
        "company": application.applicant_company,
        "email": getattr(application, "email_address", None),  # ADAPT if needed
        "contact_no": getattr(application, "contact_no", None),  # ADAPT if needed
    }


# ───────────────────────── snapshots ─────────────────────────
def build_ar_snapshot(
    application, payments, total_paid, cashier_name: str, posted_at=None
) -> dict:
    now = posted_at or datetime.now(MANILA)
    return {
        **_general_info(application),
        "payment_dates": sorted({_long_date(p.date_of_payment) for p in payments}),
        "or_numbers": [p.official_receipt_number.strip() for p in payments],
        "total_paid": float(total_paid),
        "posted_at": f"{now:%B} {now.day}, {now.year} at {now:%I:%M %p}".replace(
            " at 0", " at "
        ),
        "cashier_name": cashier_name,
        "cashier_position": "Cashier",
    }


def build_aoop_snapshot(db, application, additional_op_number: str) -> dict:
    """Figures for the Additional Order of Payment, read after the commit."""
    new_op = (
        db.query(EAppOrderOfPayment)
        .filter(
            EAppOrderOfPayment.application_uuid == application.application_uuid,
            EAppOrderOfPayment.op_number == additional_op_number,
        )
        .first()
    )
    initial_op = (
        db.query(EAppOrderOfPayment)
        .filter(
            EAppOrderOfPayment.application_uuid == application.application_uuid,
            EAppOrderOfPayment.op_type == "INITIAL",
        )
        .first()
    )
    already_paid = (
        db.query(func.coalesce(func.sum(EAppPaymentVerification.amount_paid), 0))
        .join(
            EAppOrderOfPayment,
            EAppOrderOfPayment.op_uuid == EAppPaymentVerification.op_uuid,
        )
        .filter(EAppOrderOfPayment.application_uuid == application.application_uuid)
        .scalar()
    )
    return {
        **_general_info(application),
        "op_number": additional_op_number,
        "op_uuid": new_op.op_uuid if new_op else None,
        "original_due": float(initial_op.total_amount) if initial_op else 0.0,
        "already_paid": float(already_paid or 0),
        "additional_due": float(new_op.total_amount) if new_op else 0.0,
        "remarks": (new_op.deficiency_reason if new_op else "") or "",
    }


# ───────────────────────── rendering ─────────────────────────
def _page(title: str, subtitle: str, body: str) -> str:
    sub = f"<div class='sub'>{html.escape(subtitle)}</div>" if subtitle else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 22mm 20mm; }}
      body {{ font-family: Georgia, 'Times New Roman', serif; font-size: 12.5px; color: #111; }}
      .hdr-table {{ margin-bottom: 14px; }}
      .hdr-table td {{ vertical-align: middle; }}
      .hdr-table .logos {{ width: 190px; white-space: nowrap; }}
      .hdr-table .agency {{ border-left: 1px solid #111; padding-left: 12px; line-height: 1.35; font-size: 14px; }}
      .hdr-table .agency b {{ font-size: 15px; }}
      .hdr-table .bp {{ width: 110px; text-align: right; }}
      h1 {{ text-align: center; font-size: 22px; letter-spacing: 1px; margin: 16px 0 2px; }}
      .sub {{ text-align: center; font-size: 13px; font-weight: 700; margin-bottom: 8px; }}
      h2 {{ font-size: 13px; text-decoration: underline; margin: 18px 0 4px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      td {{ padding: 3px 0; vertical-align: top; }}
      td.l {{ width: 38%; }}
      tr.total td {{ border-top: 1px solid #111; font-weight: 700; }}
      .remarks {{ border: 1px solid #111; min-height: 90px; padding: 6px; white-space: pre-wrap; }}
      .note {{ color: #c00000; font-size: 11.5px; margin-top: 18px; line-height: 1.45; }}
    </style></head><body>
      <table class="hdr-table"><tr>
        <td class="logos">{_logo_img("fda-logo.png", "110px", "64px")}
            {_logo_img("doh-logo.png", "64px", "64px")}</td>
        <td class="agency">Republic of the Philippines<br>Department of Health<br>
            <b>FOOD AND DRUG ADMINISTRATION</b></td>
        <td class="bp">{_logo_img("bagong-pilipinas-logo.png", "96px", "64px")}</td>
      </tr></table>
      <h1>{html.escape(title)}</h1>{sub}
      {body}
    </body></html>"""


def _rows(items, total_last: bool = False) -> str:
    out = []
    for i, (label, value) in enumerate(items):
        cls = " class='total'" if total_last and i == len(items) - 1 else ""
        out.append(
            f"<tr{cls}><td class='l'>{html.escape(label)}</td>"
            f"<td>{html.escape(str(value or '—'))}</td></tr>"
        )
    return "".join(out)


def _general_rows(s: dict):
    return [
        ("Reference Number:", s["reference_number"]),
        ("Authorization:", s["activity"]),
        ("Type of Application:", s["application_type"]),
        ("Classification:", s["classification"]),
        ("Name of Establishment:", s["company"]),
        ("E-mail Address:", s["email"]),
        ("Mobile Number:", s["contact_no"]),
    ]


def render_ar_html(s: dict) -> str:
    general = _general_rows(s)
    posting = [
        ("Date of Payment:", ", ".join(s["payment_dates"])),
        ("Date and Time of Posting:", s["posted_at"]),
        ("FDA Cashier Officer:", s["cashier_name"]),
        ("Position / Designation:", s["cashier_position"]),
        ("OR Number:", ", ".join(s["or_numbers"])),
        ("Total Amount Paid:", _php(s["total_paid"])),
    ]
    body = f"""
      <h2>General Information</h2><table>{_rows(general)}</table>
      <h2>VERIFICATION AND POSTING DETAILS:</h2><table>{_rows(posting)}</table>
      <p class="note">This serves as your Acknowledgement Receipt. Complete payment
      and application have been successfully submitted. Status of your application
      shall be sent through the email address indicated above.</p>"""
    return _page("ACKNOWLEDGEMENT RECEIPT", "", body)


def render_aoop_html(s: dict) -> str:
    general = [("Reference Number:", s["op_number"])] + _general_rows(s)[1:]
    payment = [
        ("Original Amount Due:", _php(s["original_due"])),
        ("Total Amount Paid:", _php(s["already_paid"])),
        ("Additional Amount Due:", _php(s["additional_due"])),
    ]
    bancnet = s["additional_due"] + BANCNET_FEE
    body = f"""
      <h2>General Information</h2><table>{_rows(general)}</table>
      <h2>Payment Details</h2><table>{_rows(payment, total_last=True)}</table>
      <h2>REMARKS / NOTES:</h2>
      <div class="remarks">{html.escape(s["remarks"])}</div>
      <div class="note">
        <p>Your application has passed the pre-assessment phase. Please pay the
        corresponding amount indicated above. Evaluation of your application shall
        commence after a payment was made and posted on our system. Kindly present
        this document upon payment thru landbank.</p>
        <p>If payment is made using Bancnet Online Bills Payment Facility
        (www.bancnetonline.com), an additional Php15.00 should be included to the
        amount due.</p>
        <p>BancNet Amount: <b>{_php(bancnet)}</b></p>
      </div>"""
    return _page("ORDER OF PAYMENT", "(ADDITIONAL)", body)


def render_pdf(kind: str, snapshot: dict) -> bytes:
    from weasyprint import HTML  # imported here so the app starts without it

    html_doc = (
        render_ar_html(snapshot) if kind == DOC_AR else render_aoop_html(snapshot)
    )
    return HTML(string=html_doc).write_pdf()


# ───────────────────────── email + log ─────────────────────────
def _send_email(to: str, subject: str, body: str, filename: str, pdf: bytes) -> None:
    from_email = os.environ["SMTP_FROM_EMAIL"]
    from_name = os.environ.get("SMTP_FROM_NAME", "")

    msg = EmailMessage()
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(
            os.environ["SMTP_USERNAME"],
            os.environ["SMTP_PASSWORD"].replace(" ", ""),
        )
        smtp.send_message(msg)


def _subject_and_body(kind: str, snapshot: dict) -> tuple[str, str, str]:
    if kind == DOC_AR:
        ref = snapshot["reference_number"]
        return (
            f"Acknowledgement Receipt - {ref}",
            f"Good day,\n\nAttached is the Acknowledgement Receipt for application "
            f"{ref}.\n\nFood and Drug Administration",
            f"Acknowledgement Receipt - {ref}.pdf",
        )
    ref = snapshot["op_number"]
    return (
        f"Additional Order of Payment - {ref}",
        f"Good day,\n\nYour payment for application {snapshot['reference_number']} "
        f"is short. Attached is the Additional Order of Payment ({ref}) for the "
        f"balance of {_php(snapshot['additional_due'])}.\n\n"
        f"Food and Drug Administration",
        f"Additional Order of Payment - {ref}.pdf",
    )


def create_notification(db, application, kind: str, snapshot: dict, source_uuid=None):
    """Adds the log row (status SENDING). Does NOT commit. Returns its uuid."""
    subject, body, _ = _subject_and_body(kind, snapshot)
    row = EAppEmailNotification(
        application_uuid=application.application_uuid,
        document_type=kind,
        source_uuid=source_uuid,
        recipient_email=snapshot.get("email") or "",
        subject=subject,
        status="SENDING",
        attempts=0,
    )
    db.add(row)
    db.flush()
    return row.notification_uuid


def _attempt(db, row, kind: str, snapshot: dict, user_uuid) -> None:
    """Send once, then log the attempt and the latest status. Commits."""
    error = None
    row.recipient_email = row.recipient_email or snapshot.get("email") or ""
    try:
        if not row.recipient_email:
            raise ValueError("No email address on the application")
        subject, body, filename = _subject_and_body(kind, snapshot)
        _send_email(
            row.recipient_email, subject, body, filename, render_pdf(kind, snapshot)
        )
    except Exception as err:
        logger.exception("Email failed: %s (%s)", row.subject, row.recipient_email)
        error = str(err)[:1000] or err.__class__.__name__

    number = (row.attempts or 0) + 1
    db.add(
        EAppEmailNotificationAttempt(
            notification_uuid=row.notification_uuid,
            attempt_number=number,
            status="FAILED" if error else "SENT",
            error_message=error,
            attempted_by_user_uuid=user_uuid,
        )
    )
    row.attempts = number
    row.status = "FAILED" if error else "SENT"
    row.last_error = error
    if not error:
        row.last_sent_at = datetime.now()
    db.commit()


def deliver_notification(notification_uuid: str, kind: str, snapshot: dict, user_uuid):
    """Background task with its own session. Never raises."""
    from app.db.session import SessionLocal  # ADAPT: your session factory

    db = SessionLocal()
    try:
        row = db.get(EAppEmailNotification, notification_uuid)
        if row:
            _attempt(db, row, kind, snapshot, user_uuid)
    except Exception:
        db.rollback()
        logger.exception("Could not write the email log for %s", notification_uuid)
    finally:
        db.close()


def rebuild_snapshot(db, row) -> dict:
    """The data for a resend, read from the database again.
    Raises ValueError when it cannot be rebuilt."""
    from app.models.user import User

    application = row.application
    if not row.source_uuid:
        raise ValueError("This email has no source record, so it cannot be resent")

    if row.document_type == DOC_AR:
        payments = (
            db.query(EAppPaymentVerification)
            .filter(EAppPaymentVerification.posting_batch_uuid == row.source_uuid)
            .all()
        )
        if not payments:
            raise ValueError("The payments for this receipt were not found")
        total = sum(float(p.amount_paid or 0) for p in payments)
        cashier = (
            db.query(User)
            .filter(User.user_uuid == payments[0].verified_by_user_uuid)
            .first()
        )
        name = (
            f"{cashier.first_name or ''} {cashier.surname or ''}".strip()
            if cashier
            else ""
        )
        stamp = getattr(payments[0], "created_at", None)  # ADAPT if named differently
        return build_ar_snapshot(application, payments, total, name, posted_at=stamp)

    if row.document_type == DOC_AOOP:
        op = (
            db.query(EAppOrderOfPayment)
            .filter(EAppOrderOfPayment.op_uuid == row.source_uuid)
            .first()
        )
        if not op:
            raise ValueError("The Additional Order of Payment was not found")
        return build_aoop_snapshot(db, application, op.op_number)

    raise ValueError("Only generated documents can be resent for now")


def send_now(db, row, kind: str, snapshot: dict, user_uuid) -> None:
    """Same as the background send, but in the caller's session (for Resend)."""
    _attempt(db, row, kind, snapshot, user_uuid)
