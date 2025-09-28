"""Utility helpers for sending SMS alerts via Twilio."""

from typing import Dict, Iterable

from ..config import settings


class TwilioConfigurationError(RuntimeError):
    """Raised when Twilio credentials or dependencies are unavailable."""


def is_configured() -> bool:
    """Return ``True`` when all Twilio settings are present."""

    return all(
        [
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_FROM_NUMBER,
        ]
    )


def send_alert(message: str, recipients: Iterable[str]) -> Dict[str, str]:
    """Send ``message`` to each phone number in ``recipients`` via Twilio."""

    if not is_configured():
        raise TwilioConfigurationError(
            "Twilio credentials are not configured. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER."
        )
    try:
        from twilio.rest import Client  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise TwilioConfigurationError(
            "The 'twilio' package is required for SMS alerts"
        ) from exc

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    results: Dict[str, str] = {}
    for phone in recipients:
        phone = phone.strip()
        if not phone:
            continue
        try:
            message_resp = client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_NUMBER,
                to=phone,
            )
            results[phone] = message_resp.sid
        except Exception as exc:  # pragma: no cover - depends on Twilio
            results[phone] = f"error: {exc}"
    return results

