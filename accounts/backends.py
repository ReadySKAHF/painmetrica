from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Бэкенд аутентификации по email вместо username
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Аутентификация пользователя по email и паролю

        Args:
            username: Email пользователя (название параметра для совместимости)
            password: Пароль

        Returns:
            User или None
        """
        # Используем email из kwargs если username не передан
        email = kwargs.get('email', username)

        if email is None or password is None:
            return None

        try:
            # Ищем пользователя по email (регистронезависимо)
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # Запускаем хэширование для защиты от timing attacks
            User().set_password(password)
            return None

        # Проверяем пароль
        if user.check_password(password):
            return user

        return None

    def get_user(self, user_id):
        """
        Получение пользователя по ID

        Args:
            user_id: ID пользователя

        Returns:
            User или None
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
