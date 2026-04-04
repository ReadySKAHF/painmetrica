import logging
import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, text: str) -> None:
    resend.api_key = settings.RESEND_API_KEY
    try:
        result = resend.Emails.send({
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "text": text,
        })
        logger.info("Email sent: %s", result)
    except Exception as e:
        logger.error("Resend error: %s | from=%s to=%s", e, settings.DEFAULT_FROM_EMAIL, to)
        raise
