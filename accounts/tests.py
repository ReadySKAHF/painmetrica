from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.backends import EmailBackend
from accounts.models import OTPCode, DoctorProfile, PatientProfile
from accounts.services.otp_service import OTPService

User = get_user_model()


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
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        self.assertTrue(otp.code.isdigit())
        self.assertEqual(len(otp.code), 4)

    def test_expires_at_устанавливается_автоматически(self):
        before = timezone.now()
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        after = timezone.now()
        self.assertGreater(otp.expires_at, before + timedelta(minutes=4))
        self.assertLess(otp.expires_at, after + timedelta(minutes=6))

    def test_is_valid_возвращает_true_для_нового_кода(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        self.assertTrue(otp.is_valid())

    def test_is_valid_возвращает_false_для_использованного(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        otp.is_used = True
        otp.save()
        self.assertFalse(otp.is_valid())

    def test_is_valid_возвращает_false_для_просроченного(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
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
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        success, error = OTPService.verify_otp(self.user, otp.code, purpose='login')
        self.assertTrue(success)
        self.assertIsNone(error)

    def test_verify_otp_помечает_код_использованным(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        OTPService.verify_otp(self.user, otp.code, purpose='login')
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_otp_неверный_код(self):
        OTPCode.objects.create(user=self.user, purpose='login')
        success, error = OTPService.verify_otp(self.user, '0000', purpose='login')
        self.assertFalse(success)
        self.assertIsNotNone(error)

    def test_verify_otp_просроченный_код(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save()
        success, error = OTPService.verify_otp(self.user, otp.code, purpose='login')
        self.assertFalse(success)

    def test_verify_otp_повторное_использование_запрещено(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
        OTPService.verify_otp(self.user, otp.code, purpose='login')
        success, error = OTPService.verify_otp(self.user, otp.code, purpose='login')
        self.assertFalse(success)

    def test_has_valid_otp_true_для_действующего(self):
        OTPCode.objects.create(user=self.user, purpose='login')
        self.assertTrue(OTPService.has_valid_otp(self.user, purpose='login'))

    def test_has_valid_otp_false_если_нет_кодов(self):
        self.assertFalse(OTPService.has_valid_otp(self.user, purpose='login'))

    def test_has_valid_otp_false_для_просроченного(self):
        otp = OTPCode.objects.create(user=self.user, purpose='login')
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
