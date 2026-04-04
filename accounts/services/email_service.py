import resend
from django.conf import settings


def send_email(to: str, subject: str, text: str) -> None:
    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "text": text,
    })
