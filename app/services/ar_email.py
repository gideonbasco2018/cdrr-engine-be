import html
import logging
import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from email.utils import formataddr

logger = logging.getLogger(__name__)

MANILA = ZoneInfo("Asia/Manila")


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
        import json

        try:
            data = json.loads(data)
        except ValueError:
            data = {}
    return data if isinstance(data, dict) else {}


def build_ar_snapshot(application, payments, total_paid, cashier_name: str) -> dict:
    """Plain data for the receipt. Call after the payment is committed, while
    the session is still open, and pass the result to the background task."""
    now = datetime.now(MANILA)
    return {
        "reference_number": application.reference_number,
        "activity": application.activity,
        "application_type": application.application_type,
        "classification": _form_data(application).get("Classification"),
        "company": application.applicant_company,
        "email": getattr(application, "email_address", None),  # ADAPT if needed
        "contact_no": getattr(application, "contact_no", None),  # ADAPT if needed
        "payment_dates": sorted({_long_date(p.date_of_payment) for p in payments}),
        "or_numbers": [p.official_receipt_number.strip() for p in payments],
        "total_paid": float(total_paid),
        "posted_at": f"{now:%B} {now.day}, {now.year} at {now:%I:%M %p}".replace(
            " at 0", " at "
        ),
        "cashier_name": cashier_name,
        "cashier_position": "Cashier",
    }


def render_ar_html(s: dict) -> str:
    e = lambda v: html.escape(str(v or "—"))  # noqa: E731

    def rows(items):
        return "".join(
            f"<tr><td class='l'>{html.escape(label)}</td><td>{e(value)}</td></tr>"
            for label, value in items
        )

    general = [
        ("Reference Number:", s["reference_number"]),
        ("Authorization:", s["activity"]),
        ("Type of Application:", s["application_type"]),
        ("Classification:", s["classification"]),
        ("Name of Establishment:", s["company"]),
        ("E-mail Address:", s["email"]),
        ("Mobile Number:", s["contact_no"]),
    ]
    posting = [
        ("Date of Payment:", ", ".join(s["payment_dates"])),
        ("Date and Time of Posting:", s["posted_at"]),
        ("FDA Cashier Officer:", s["cashier_name"]),
        ("Position / Designation:", s["cashier_position"]),
        ("OR Number:", ", ".join(s["or_numbers"])),
        ("Total Amount Paid:", _php(s["total_paid"])),
    ]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      @page {{ size: A4; margin: 22mm 20mm; }}
      body {{ font-family: Georgia, 'Times New Roman', serif; font-size: 12.5px; color: #111; }}
      .hdr {{ text-align: center; line-height: 1.35; margin-bottom: 14px; }}
      .hdr b {{ font-size: 15px; }}
      h1 {{ text-align: center; font-size: 22px; letter-spacing: 1px; margin: 16px 0; }}
      h2 {{ font-size: 13px; text-decoration: underline; margin: 18px 0 4px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      td {{ padding: 3px 0; vertical-align: top; }}
      td.l {{ width: 38%; }}
      .note {{ color: #c00000; font-size: 11.5px; margin-top: 22px; }}
    </style></head><body>
      <div class="hdr">Republic of the Philippines<br>Department of Health<br>
        <b>FOOD AND DRUG ADMINISTRATION</b></div>
      <h1>ACKNOWLEDGEMENT RECEIPT</h1>
      <h2>General Information</h2><table>{rows(general)}</table>
      <h2>VERIFICATION AND POSTING DETAILS:</h2><table>{rows(posting)}</table>
      <p class="note">This serves as your Acknowledgement Receipt. Complete payment
      and application have been successfully submitted. Status of your application
      shall be sent through the email address indicated above.</p>
    </body></html>"""


def render_ar_pdf(snapshot: dict) -> bytes:
    from weasyprint import HTML  # imported here so the app starts without it

    return HTML(string=render_ar_html(snapshot)).write_pdf()


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


def send_acknowledgement_receipt(snapshot: dict) -> None:
    """Background task. Never raises: a failed email must not affect the
    payment, which is already committed."""
    ref = snapshot["reference_number"]
    to = snapshot.get("email")
    if not to:
        logger.warning("AR for %s not sent: no email address on the application", ref)
        return
    try:
        pdf = render_ar_pdf(snapshot)
        _send_email(
            to=to,
            subject=f"Acknowledgement Receipt - {ref}",
            body=(
                f"Good day,\n\nAttached is the Acknowledgement Receipt for "
                f"application {ref}.\n\nFood and Drug Administration"
            ),
            filename=f"Acknowledgement Receipt - {ref}.pdf",
            pdf=pdf,
        )
        logger.info("AR for %s sent to %s", ref, to)
    except Exception:
        logger.exception("Failed to send the AR for %s to %s", ref, to)
