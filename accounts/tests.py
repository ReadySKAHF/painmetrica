from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.backends import EmailBackend
from accounts.models import OTPCode, DoctorProfile, PatientProfile
from accounts.services.otp_service import OTPService

User = get_user_model()

_NO_REDIS = dict(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    SESSION_ENGINE='django.contrib.sessions.backends.db',
)


# ─────────────────────────────────────────────
# Вспомогательные фабрики
# ─────────────────────────────────────────────

def make_doctor(**kwargs):
    defaults = dict(
        email='doctor@test.com',
        password='TestPass123!',
        first_name='Иван',
        last_name='Иванов',
        user_type='doctor',
        is_email_verified=True,
    )
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_patient(**kwargs):
    defaults = dict(
        email='patient@test.com',
        password='TestPass123!',
        first_name='Пётр',
        last_name='Петров',
        user_type='patient',
        is_email_verified=True,
    )
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


# ─────────────────────────────────────────────
# Модель User
# ─────────────────────────────────────────────

class UserModelTests(TestCase):

    def test_создание_доктора(self):
        user = make_doctor()
        self.assertEqual(user.email, 'doctor@test.com')
        self.assertEqual(user.user_type, 'doctor')
        self.assertTrue(user.is_email_verified)

    def test_email_является_username(self):
        user = make_doctor()
        self.assertEqual(user.USERNAME_FIELD, 'email')
        self.assertIsNone(user.username)

    def test_get_full_name_с_отчеством(self):
        user = make_doctor(middle_name='Сергеевич')
        self.assertEqual(user.get_full_name(), 'Иванов Иван Сергеевич')

    def test_get_full_name_без_отчества(self):
        user = make_doctor()
        self.assertEqual(user.get_full_name(), 'Иванов Иван')

    def test_email_уникален(self):
        make_doctor()
        with self.assertRaises(Exception):
            make_doctor()

    def test_создание_пациента(self):
        user = make_patient()
        self.assertEqual(user.user_type, 'patient')

    def test_неверифицированный_пользователь_по_умолчанию(self):
        user = User.objects.create_user(
            email='new@test.com',
            password='pass',
            first_name='А',
            last_name='Б',
            user_type='doctor',
        )
        self.assertFalse(user.is_email_verified)


# ─────────────────────────────────────────────
# Модель OTPCode
# ─────────────────────────────────────────────

class OTPCodeModelTests(TestCase):

    def setUp(self):
        self.user = make_doctor()

    def test_код_генерируется_автоматически(self):
        otp, code = OTPCode.create_for_user(self.user, 'login')
        self.assertTrue(code.isdigit())
        self.assertEqual(len(code), 4)
        self.assertEqual(len(otp.code_hash), 64)

    def test_expires_at_устанавливается_автоматически(self):
        before = timezone.now()
        otp, _ = OTPCode.create_for_user(self.user, 'login')
        after = timezone.now()
        self.assertGreater(otp.expires_at, before + timedelta(minutes=4))
        self.assertLess(otp.expires_at, after + timedelta(minutes=6))

    def test_is_valid_возвращает_true_для_нового_кода(self):
        otp, _ = OTPCode.create_for_user(self.user, 'login')
        self.assertTrue(otp.is_valid())

    def test_is_valid_возвращает_false_для_использованного(self):
        otp, _ = OTPCode.create_for_user(self.user, 'login')
        otp.is_used = True
        otp.save()
        self.assertFalse(otp.is_valid())

    def test_is_valid_возвращает_false_для_просроченного(self):
        otp, _ = OTPCode.create_for_user(self.user, 'login')
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        self.assertFalse(otp.is_valid())

    def test_generate_code_возвращает_четыре_цифры(self):
        code = OTPCode.generate_code()
        self.assertEqual(len(code), 4)
        self.assertTrue(code.isdigit())
        self.assertGreaterEqual(int(code), 1000)
        self.assertLessEqual(int(code), 9999)


# ─────────────────────────────────────────────
# OTPService
# ─────────────────────────────────────────────

class OTPServiceTests(TestCase):

    def setUp(self):
        self.user = make_doctor()

    def test_verify_otp_успешная_верификация(self):
        otp, code = OTPCode.create_for_user(self.user, 'login')
        success, error = OTPService.verify_otp(self.user, code, purpose='login')
        self.assertTrue(success)
        self.assertIsNone(error)

    def test_verify_otp_помечает_код_использованным(self):
        otp, code = OTPCode.create_for_user(self.user, 'login')
        OTPService.verify_otp(self.user, code, purpose='login')
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_otp_неверный_код(self):
        OTPCode.create_for_user(self.user, 'login')
        success, error = OTPService.verify_otp(self.user, '000000', purpose='login')
        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_verify_otp_просроченный_код(self):
        otp, code = OTPCode.create_for_user(self.user, 'login')
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        success, error = OTPService.verify_otp(self.user, code, purpose='login')
        self.assertFalse(success)

    def test_verify_otp_повторное_использование_запрещено(self):
        otp, code = OTPCode.create_for_user(self.user, 'login')
        OTPService.verify_otp(self.user, code, purpose='login')
        success, error = OTPService.verify_otp(self.user, code, purpose='login')
        self.assertFalse(success)

    def test_has_valid_otp_true_для_действующего(self):
        OTPCode.create_for_user(self.user, 'login')
        self.assertTrue(OTPService.has_valid_otp(self.user, purpose='login'))

    def test_has_valid_otp_false_если_нет_кодов(self):
        self.assertFalse(OTPService.has_valid_otp(self.user, purpose='login'))

    def test_has_valid_otp_false_для_просроченного(self):
        otp, _ = OTPCode.create_for_user(self.user, 'login')
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        self.assertFalse(OTPService.has_valid_otp(self.user, purpose='login'))


# ─────────────────────────────────────────────
# EmailBackend
# ─────────────────────────────────────────────

class EmailBackendTests(TestCase):

    def setUp(self):
        self.user = make_doctor()
        self.backend = EmailBackend()

    def test_аутентификация_по_email_и_паролю(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        user = self.backend.authenticate(request, email='doctor@test.com', password='TestPass123!')
        self.assertIsNotNone(user)
        self.assertEqual(user.pk, self.user.pk)

    def test_неверный_пароль(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        user = self.backend.authenticate(request, email='doctor@test.com', password='WrongPass!')
        self.assertIsNone(user)

    def test_несуществующий_email(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        user = self.backend.authenticate(request, email='nobody@test.com', password='TestPass123!')
        self.assertIsNone(user)

    def test_неверифицированный_пользователь_аутентифицируется_по_паролю(self):
        """Бэкенд проверяет только пароль; блокировка по is_email_verified — в OTP-флоу."""
        User.objects.create_user(
            email='unverified@test.com',
            password='TestPass123!',
            first_name='А',
            last_name='Б',
            user_type='doctor',
            is_email_verified=False,
        )
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        user = self.backend.authenticate(request, email='unverified@test.com', password='TestPass123!')
        self.assertIsNotNone(user)


# ─────────────────────────────────────────────
# Представления аутентификации
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class LoginViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_doctor()
        self.url = reverse('accounts:login')

    def test_страница_входа_открывается(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_авторизованный_редиректится_на_дашборд(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_неверные_данные_возвращают_форму(self):
        response = self.client.post(self.url, {'email': 'doctor@test.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)

    def test_верные_данные_сохраняют_user_id_в_сессии(self):
        response = self.client.post(self.url, {
            'email': 'doctor@test.com',
            'password': 'TestPass123!',
        })
        self.assertIn('login_user_id', self.client.session)


@override_settings(**_NO_REDIS)
class RegisterStepOneViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:register_step_one')

    def test_страница_регистрации_открывается(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_валидные_данные_сохраняются_в_сессию(self):
        response = self.client.post(self.url, {
            'first_name': 'Иван',
            'middle_name': '',
            'last_name': 'Иванов',
            'email': 'newdoctor@test.com',
            'password': 'TestPass123!',
        })
        self.assertIn('registration_data', self.client.session)
        self.assertRedirects(response, reverse('accounts:register_step_two'))

    def test_дублирующий_email_не_проходит(self):
        make_doctor()
        response = self.client.post(self.url, {
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'email': 'doctor@test.com',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────
# PatientInvitation
# ─────────────────────────────────────────────

class PatientInvitationModelTests(TestCase):

    def setUp(self):
        from accounts.models import PatientInvitation
        self.PatientInvitation = PatientInvitation
        self.doctor = make_doctor()

    def test_создание_приглашения(self):
        inv = self.PatientInvitation.objects.create(
            doctor=self.doctor,
            email='patient@clinic.com',
        )
        self.assertIsNotNone(inv.token)
        self.assertEqual(inv.email, 'patient@clinic.com')
        self.assertFalse(inv.is_used)

    def test_expires_at_устанавливается_автоматически(self):
        from django.utils import timezone
        before = timezone.now()
        inv = self.PatientInvitation.objects.create(doctor=self.doctor, email='p@test.com')
        self.assertGreater(inv.expires_at, before)

    def test_is_valid_для_нового_приглашения(self):
        inv = self.PatientInvitation.objects.create(doctor=self.doctor, email='p@test.com')
        self.assertTrue(inv.is_valid())

    def test_is_valid_false_если_использовано(self):
        inv = self.PatientInvitation.objects.create(doctor=self.doctor, email='p@test.com')
        inv.is_used = True
        inv.save()
        self.assertFalse(inv.is_valid())

    def test_is_valid_false_если_просрочено(self):
        from django.utils import timezone
        from datetime import timedelta
        inv = self.PatientInvitation.objects.create(doctor=self.doctor, email='p@test.com')
        inv.expires_at = timezone.now() - timedelta(days=1)
        inv.save()
        self.assertFalse(inv.is_valid())

    def test_строковое_представление(self):
        inv = self.PatientInvitation.objects.create(doctor=self.doctor, email='p@test.com')
        self.assertIn('p@test.com', str(inv))

    def test_token_является_uuid_и_уникален(self):
        import uuid
        inv1 = self.PatientInvitation.objects.create(doctor=self.doctor, email='p1@test.com')
        inv2 = self.PatientInvitation.objects.create(doctor=self.doctor, email='p2@test.com')
        self.assertIsInstance(inv1.token, uuid.UUID)
        self.assertNotEqual(inv1.token, inv2.token)


# ─────────────────────────────────────────────
# AccountDeletionService
# ─────────────────────────────────────────────

class AccountDeletionServiceTests(TestCase):

    def setUp(self):
        from accounts.models import DoctorProfile, PatientProfile
        from patients.models import Patient
        from accounts.services.account_deletion_service import deactivate_user_account
        self.deactivate_user_account = deactivate_user_account
        self.DoctorProfile = DoctorProfile
        self.PatientProfile = PatientProfile
        self.Patient = Patient

    def _make_doctor_with_profile(self, email='doc@test.com'):
        doctor = User.objects.create_user(
            email=email, password='TestPass123!',
            first_name='Иван', last_name='Иванов',
            user_type='doctor', is_email_verified=True,
        )
        self.DoctorProfile.objects.create(
            user=doctor,
            specialty='Невролог',
            position='Врач',
            workplace='Клиника',
            city='Москва',
        )
        return doctor

    def _make_patient_with_profile(self, email='pat@test.com', doctor=None):
        user = User.objects.create_user(
            email=email, password='TestPass123!',
            first_name='Пётр', last_name='Петров',
            user_type='patient', is_email_verified=True,
        )
        self.PatientProfile.objects.create(user=user)
        self.Patient.objects.create(user=user, assigned_doctor=doctor)
        return user

    def test_деактивация_доктора_очищает_персональные_данные(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(doctor)
        doctor.refresh_from_db()
        self.assertEqual(doctor.first_name, '')
        self.assertEqual(doctor.last_name, '')
        self.assertFalse(doctor.is_active)
        self.assertFalse(doctor.is_email_verified)

    def test_деактивация_доктора_меняет_email(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        pk = doctor.pk
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(doctor)
        doctor.refresh_from_db()
        self.assertEqual(doctor.email, f'deleted_{pk}@deleted.invalid')

    def test_деактивация_доктора_делает_пароль_неиспользуемым(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(doctor)
        doctor.refresh_from_db()
        self.assertFalse(doctor.has_usable_password())

    def test_деактивация_доктора_открепляет_пациентов(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        patient_user = self._make_patient_with_profile(doctor=doctor)
        patient = self.Patient.objects.get(user=patient_user)
        self.assertEqual(patient.assigned_doctor, doctor)
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(doctor)
        patient.refresh_from_db()
        self.assertIsNone(patient.assigned_doctor)

    def test_деактивация_доктора_очищает_профиль(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(doctor)
        profile = self.DoctorProfile.objects.get(user=doctor)
        self.assertEqual(profile.specialty, '')
        self.assertEqual(profile.position, '')
        self.assertEqual(profile.workplace, '')

    def test_деактивация_пациента_очищает_персональные_данные(self):
        from unittest.mock import patch
        patient_user = self._make_patient_with_profile()
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(patient_user)
        patient_user.refresh_from_db()
        self.assertEqual(patient_user.first_name, '')
        self.assertFalse(patient_user.is_active)
        self.assertFalse(patient_user.is_email_verified)

    def test_деактивация_пациента_архивирует_запись(self):
        from unittest.mock import patch
        patient_user = self._make_patient_with_profile()
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(patient_user)
        patient = self.Patient.objects.get(user=patient_user)
        self.assertTrue(patient.is_archived)
        self.assertIsNotNone(patient.archived_at)
        self.assertIsNotNone(patient.scheduled_deletion_at)

    def test_деактивация_пациента_открепляет_доктора(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile()
        patient_user = self._make_patient_with_profile(doctor=doctor)
        with patch('accounts.services.account_deletion_service.send_email'):
            self.deactivate_user_account(patient_user)
        patient = self.Patient.objects.get(user=patient_user)
        self.assertIsNone(patient.assigned_doctor)

    def test_неверный_тип_пользователя_вызывает_ошибку(self):
        from unittest.mock import patch
        user = User.objects.create_user(
            email='admin2@test.com', password='pass',
            first_name='А', last_name='Б', user_type='doctor',
        )
        user.user_type = 'unknown'
        with self.assertRaises(ValueError):
            self.deactivate_user_account(user)

    def test_возвращает_email_до_деактивации(self):
        from unittest.mock import patch
        doctor = self._make_doctor_with_profile(email='original@test.com')
        with patch('accounts.services.account_deletion_service.send_email'):
            returned_email = self.deactivate_user_account(doctor)
        self.assertEqual(returned_email, 'original@test.com')
