from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random
import uuid


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели User"""

    def create_user(self, email, password=None, **extra_fields):
        """Создание обычного пользователя"""
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Создание суперпользователя"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser должен иметь is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Кастомная модель пользователя с email вместо username"""

    USER_TYPE_CHOICES = [
        ('doctor', 'Доктор'),
        ('patient', 'Пациент'),
    ]

    username = None  # Убираем username
    email = models.EmailField('Email адрес', unique=True)
    user_type = models.CharField('Тип пользователя', max_length=10, choices=USER_TYPE_CHOICES)

    # Русские ФИО
    first_name = models.CharField('Имя', max_length=150)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    last_name = models.CharField('Фамилия', max_length=150)

    is_email_verified = models.BooleanField('Email подтвержден', default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'user_type']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        """Возвращает полное ФИО"""
        if self.middle_name:
            return f'{self.last_name} {self.first_name} {self.middle_name}'
        return f'{self.last_name} {self.first_name}'


class DoctorProfile(models.Model):
    """Профиль доктора"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialty = models.CharField('Специальность', max_length=200)
    position = models.CharField('Должность', max_length=200)
    workplace = models.CharField('Место работы', max_length=300)
    city = models.CharField('Город', max_length=100)
    area_of_interest = models.TextField('Область интересов', blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Профиль доктора'
        verbose_name_plural = 'Профили докторов'

    def __str__(self):
        return f'Доктор: {self.user.get_full_name()}'


class PatientProfile(models.Model):
    """Профиль пациента"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField('Дата рождения', null=True, blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    address = models.TextField('Адрес', blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Профиль пациента'
        verbose_name_plural = 'Профили пациентов'

    def __str__(self):
        return f'Пациент: {self.user.get_full_name()}'


class OTPCode(models.Model):
    """Модель для хранения OTP кодов"""

    PURPOSE_CHOICES = [
        ('registration', 'Регистрация'),
        ('login', 'Вход'),
        ('password_reset', 'Сброс пароля'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField('OTP код', max_length=4)
    purpose = models.CharField('Назначение', max_length=20, choices=PURPOSE_CHOICES)
    is_used = models.BooleanField('Использован', default=False)
    expires_at = models.DateTimeField('Истекает')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'OTP код'
        verbose_name_plural = 'OTP коды'
        ordering = ['-created_at']

    def __str__(self):
        return f'OTP {self.code} для {self.user.email} ({self.purpose})'

    @classmethod
    def generate_code(cls):
        """Генерация 4-значного OTP кода"""
        return str(random.randint(1000, 9999))

    def is_valid(self):
        """Проверка действительности кода"""
        return not self.is_used and timezone.now() < self.expires_at

    def save(self, *args, **kwargs):
        """Автоматическая установка времени истечения"""
        if not self.pk and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)


class PatientInvitation(models.Model):
    """Приглашение пациента к самостоятельной регистрации"""

    token = models.UUIDField('Токен', default=uuid.uuid4, unique=True, editable=False)
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        limit_choices_to={'user_type': 'doctor'},
        verbose_name='Доктор'
    )
    email = models.EmailField('Email пациента')
    is_used = models.BooleanField('Использовано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    expires_at = models.DateTimeField('Истекает')

    class Meta:
        verbose_name = 'Приглашение пациента'
        verbose_name_plural = 'Приглашения пациентов'
        ordering = ['-created_at']

    def __str__(self):
        return f'Приглашение для {self.email} от {self.doctor.get_full_name()}'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
