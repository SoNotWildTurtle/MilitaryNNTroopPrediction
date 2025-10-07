"""Utility helpers for sending email alerts via SMTP."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Dict, Iterable

from ..config import settings


class EmailConfigurationError(RuntimeError):
    """Raised when SMTP credentials or configuration are missing."""


def is_configured() -> bool:
    """Return ``True`` when the minimum SMTP settings are present."""

    return bool(settings.EMAIL_SMTP_HOST and settings.EMAIL_FROM_ADDRESS)


def send_alert(subject: str, message: str, recipients: Iterable[str]) -> Dict[str, str]:
    """Send an email alert to ``recipients`` using configured SMTP settings."""

    if not is_configured():
        raise EmailConfigurationError(
            "SMTP settings are not configured. Set EMAIL_SMTP_HOST and EMAIL_FROM_ADDRESS."
        )

    addresses = [addr.strip() for addr in recipients if addr and addr.strip()]
    if not addresses:
        return {}

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = settings.EMAIL_FROM_ADDRESS
    email["To"] = ", ".join(addresses)
    email.set_content(message)

    host = settings.EMAIL_SMTP_HOST
    port = settings.EMAIL_SMTP_PORT
    username = settings.EMAIL_SMTP_USERNAME
    password = settings.EMAIL_SMTP_PASSWORD
    use_tls = settings.EMAIL_USE_TLS

    try:
        if use_tls:
            with smtplib.SMTP(host, port, timeout=15) as client:
                client.starttls()
                if username and password:
                    client.login(username, password)
                client.send_message(email)
        else:
            with smtplib.SMTP(host, port, timeout=15) as client:
                if username and password:
                    client.login(username, password)
                client.send_message(email)
    except Exception as exc:  # pragma: no cover - network/SMTP errors environment-dependent
        raise EmailConfigurationError(str(exc)) from exc

    return {addr: "sent" for addr in addresses}
