import logging

from accounts.services.email_service import send_email

logger = logging.getLogger(__name__)


def notify_doctor_test_completed(session, result_url: str) -> None:
    """Отправляет врачу письмо о завершении теста пациентом.

    Вызывается только когда тест завершил пользователь с ролью «пациент».
    Ошибка отправки не прерывает основной поток.
    """
    doctor = getattr(session.patient, 'assigned_doctor', None)
    if not doctor or not doctor.email:
        return

    patient_name = session.patient.user.get_full_name()
    test_title = session.test.title

    subject = f'Ваш пациент прошел {test_title}'
    body = (
        f'Пациент {patient_name} завершил сессию комплексного тестирования болевого синдрома.\n'
        f'Результаты вы можете увидеть по ссылке: {result_url}'
    )

    try:
        send_email(to=doctor.email, subject=subject, text=body)
    except Exception:
        logger.exception(
            'Не удалось отправить уведомление врачу %s о завершении теста сессии %s',
            doctor.email, session.pk,
        )
