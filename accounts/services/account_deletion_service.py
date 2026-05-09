import logging
from datetime import timedelta

from django.utils import timezone

from accounts.services.email_service import send_email

logger = logging.getLogger(__name__)

_TWENTY_FIVE_YEARS = timedelta(days=9131)  # 25 лет с учётом високосных

_DOCTOR_SUBJECT = 'Ваш аккаунт был удален из системы Painmetrica'
_DOCTOR_BODY = (
    'Ваш аккаунт был успешно удален из системы Painmetrica. '
    'Ваши email, ФИО, пароль, должность, специальность, место работы, '
    'город и сфера интересов были стерты из базы данных.'
)

_PATIENT_SUBJECT = 'Ваш аккаунт был удален из системы Painmetrica'
_PATIENT_BODY = (
    'Ваш аккаунт был успешно удален из системы Painmetrica.\n'
    'Ваши email, ФИО, пароль, должность, специальность, место работы, '
    'город и сфера интересов были стерты из базы данных.\n'
    'Ваши диагноз; локализация боли; длительность боли; результаты тестовых сессий; '
    'сформированные вашим врачом заключения - архивированы. '
    'Они будут храниться на серверах Painmetrica и будут физически удалены через 25 лет.'
)


def deactivate_user_account(user):
    """
    Деактивирует аккаунт пользователя согласно политике удаления данных.
    Возвращает email пользователя до его стирания.
    """
    if user.user_type == 'doctor':
        return _deactivate_doctor(user)
    if user.user_type == 'patient':
        return _deactivate_patient(user)
    raise ValueError(f'Неизвестный тип пользователя: {user.user_type}')


def _terminate_sessions(user):
    from django.contrib.sessions.backends.cache import SessionStore
    from accounts.models import UserSession
    sessions = UserSession.objects.filter(user=user)
    for s in sessions:
        SessionStore(s.session_key).delete()
    sessions.delete()


def _deactivate_doctor(user):
    from patients.models import Patient

    _terminate_sessions(user)

    # Получаем учреждение доктора до очистки профиля
    doctor_org = None
    try:
        doctor_org = user.doctor_profile.organization
    except Exception:
        pass

    # Пациентам без учреждения — назначаем учреждение доктора, затем открепляем доктора
    if doctor_org:
        Patient.objects.filter(assigned_doctor=user, organization__isnull=True).update(
            organization=doctor_org,
            assigned_doctor=None,
        )
    Patient.objects.filter(assigned_doctor=user).update(assigned_doctor=None)

    email = user.email

    user.email = f'deleted_{user.pk}@deleted.invalid'
    user.first_name = ''
    user.middle_name = ''
    user.last_name = ''
    user.set_unusable_password()
    user.is_active = False
    user.is_email_verified = False
    user.save()

    try:
        p = user.doctor_profile
        p.specialty = ''
        p.position = ''
        p.workplace = ''
        p.city = ''
        p.area_of_interest = ''
        p.organization = None
        p.save()
    except Exception:
        logger.warning('DoctorProfile not found for user pk=%s', user.pk)

    _send_notification(email, _DOCTOR_SUBJECT, _DOCTOR_BODY)
    return email


def _deactivate_patient(user):
    from patients.models import Patient

    _terminate_sessions(user)
    email = user.email

    user.email = f'deleted_{user.pk}@deleted.invalid'
    user.first_name = ''
    user.middle_name = ''
    user.last_name = ''
    user.set_unusable_password()
    user.is_active = False
    user.is_email_verified = False
    user.save()

    try:
        pp = user.patient_profile
        pp.date_of_birth = None
        pp.phone = ''
        pp.address = ''
        pp.save()
    except Exception:
        logger.warning('PatientProfile not found for user pk=%s', user.pk)

    try:
        patient = user.patient_record
        # Наследуем учреждение от доктора, если у пациента не задано
        if not patient.organization and patient.assigned_doctor:
            try:
                patient.organization = patient.assigned_doctor.doctor_profile.organization
            except Exception:
                pass
        patient.assigned_doctor = None
        now = timezone.now()
        patient.is_archived = True
        patient.archived_at = now
        patient.scheduled_deletion_at = now + _TWENTY_FIVE_YEARS
        patient.save()
    except Patient.DoesNotExist:
        logger.warning('Patient record not found for user pk=%s', user.pk)

    _send_notification(email, _PATIENT_SUBJECT, _PATIENT_BODY)
    return email


def _send_notification(email, subject, body):
    try:
        send_email(to=email, subject=subject, text=body)
    except Exception as exc:
        logger.error('Не удалось отправить уведомление об удалении на %s: %s', email, exc)
