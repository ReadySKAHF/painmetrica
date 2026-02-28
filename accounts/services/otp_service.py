from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from accounts.models import OTPCode


class OTPService:
    """Сервис для работы с OTP кодами"""

    @staticmethod
    def generate_and_send_otp(user, purpose='registration'):
        """
        Генерация и отправка OTP кода на email пользователя

        Args:
            user: Пользователь
            purpose: Назначение кода ('registration', 'login', 'password_reset')

        Returns:
            OTPCode: Созданный OTP код
        """
        # Создаем новый OTP код
        otp = OTPCode.objects.create(
            user=user,
            purpose=purpose
        )

        # Формируем текст письма
        purpose_text = {
            'registration': 'регистрации',
            'login': 'входа в систему',
            'password_reset': 'сброса пароля',
        }

        subject = f'Код подтверждения для {purpose_text.get(purpose, "верификации")}'
        message = f"""
Здравствуйте, {user.first_name}!

Ваш код подтверждения: {otp.code}

Код действителен в течение 5 минут.

Если вы не запрашивали этот код, проигнорируйте это письмо.

--
Система Painmetrica
        """.strip()

        # Отправляем email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return otp

    @staticmethod
    def verify_otp(user, code, purpose='registration'):
        """
        Проверка OTP кода

        Args:
            user: Пользователь
            code: OTP код для проверки
            purpose: Назначение кода

        Returns:
            tuple: (bool: успех, str: сообщение об ошибке или None)
        """
        try:
            # Ищем код пользователя
            otp = OTPCode.objects.filter(
                user=user,
                code=code,
                purpose=purpose,
                is_used=False
            ).latest('created_at')

            # Проверяем срок действия
            if not otp.is_valid():
                if timezone.now() > otp.expires_at:
                    return False, 'Код истек. Запросите новый код.'
                return False, 'Код уже использован.'

            # Помечаем код как использованный
            otp.is_used = True
            otp.save()

            return True, None

        except OTPCode.DoesNotExist:
            return False, 'Неверный код.'

    @staticmethod
    def has_valid_otp(user, purpose='registration'):
        """
        Проверка наличия действующего OTP кода

        Args:
            user: Пользователь
            purpose: Назначение кода

        Returns:
            bool: Есть ли действующий код
        """
        return OTPCode.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
            expires_at__gt=timezone.now()
        ).exists()
