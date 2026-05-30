from django.utils import timezone
from accounts.models import OTPCode
from accounts.services.email_service import send_email


class OTPService:
    """Сервис для работы с OTP кодами"""

    @staticmethod
    def generate_and_send_otp(user, purpose='registration'):
        """Генерирует 6-значный OTP, сохраняет SHA-256 хеш в БД и отправляет
        открытый код пользователю по email."""
        OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now()
        ).update(is_used=True)

        otp, plain_code = OTPCode.create_for_user(user, purpose)

        purpose_text = {
            'registration': 'регистрации',
            'login': 'входа в систему',
            'password_reset': 'сброса пароля',
        }

        subject = f'Код подтверждения для {purpose_text.get(purpose, "верификации")}'
        message = f"""
Здравствуйте, {user.first_name}!

Ваш код подтверждения: {plain_code}

Код действителен в течение 5 минут.

Если вы не запрашивали этот код, проигнорируйте это письмо.

--
Система Painmetrica
        """.strip()

        send_email(to=user.email, subject=subject, text=message)

        return otp

    @staticmethod
    def verify_otp(user, code, purpose='registration'):
        """Проверяет OTP через HMAC-сравнение хешей (защита от timing attack).

        Returns:
            tuple: (bool успех, str|None сообщение об ошибке)
        """
        try:
            otp = OTPCode.objects.filter(
                user=user,
                purpose=purpose,
                is_used=False,
                expires_at__gt=timezone.now(),
            ).latest('created_at')
        except OTPCode.DoesNotExist:
            return False, 'Неверный код.'

        if not otp.check_code(code):
            return False, 'Неверный код.'

        otp.is_used = True
        otp.save(update_fields=['is_used'])
        return True, None

    @staticmethod
    def has_valid_otp(user, purpose='registration'):
        """Проверяет наличие действующего OTP кода."""
        return OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now()
        ).exists()
