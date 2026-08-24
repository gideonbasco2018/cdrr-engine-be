"""
Basic SMTP email sender.
Reads SMTP_HOST / SMTP_PORT / SMTP_USERNAME / SMTP_PASSWORD /
SMTP_FROM_EMAIL / SMTP_FROM_NAME from settings (sourced from .env).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from app.core.config import settings


def send_email(to: str, subject: str, body: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to], msg.as_string())
