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


def send_verification_email(user) -> None:
    """Письмо доктору о успешной верификации аккаунта."""
    name_io = f"{user.first_name} {user.middle_name}".strip() if user.middle_name else user.first_name
    text = (
        f"Уважаемый(-ая) {name_io}.\n\n"
        "Ваша учётная запись в системе Painmetrica прошла верификацию и полностью активирована. "
        "Теперь вам доступны все функции системы:\n\n"
        "– добавление пациентов и ведение их карточек;\n"
        "– проведение диагностических тестов (VAS, DN4, CSI, HADS, PAINAD, NCS-R);\n"
        "– формирование консультативных заключений;\n"
        "– просмотр истории тестирования и динамики состояния пациентов.\n\n"
        "Войти в систему можно по адресу: painmetrica.by\n\n"
        "Если у вас возникнут вопросы по работе с системой, воспользуйтесь инструкцией пользователя "
        "в разделе «Документы» вашего личного кабинета или обратитесь в техническую поддержку "
        "через кнопку «Тех. поддержка» в правом верхнем углу.\n\n"
        "С уважением,\n"
        "Команда Painmetrica"
    )
    send_email(user.email, "Вы прошли верификацию в системе Painmetrica", text)
