from django.db import models
from django.conf import settings


class Patient(models.Model):
    """Модель пациента для управления докторами"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'patient'},
        related_name='patient_record',
        verbose_name='Пользователь'
    )
    assigned_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='patients',
        verbose_name='Лечащий врач'
    )
    medical_history = models.TextField('Медицинская история', blank=True)
    pain_location = models.CharField('Локализация боли', max_length=200, blank=True)
    pain_duration = models.CharField('Длительность боли', max_length=20, blank=True)
    notes = models.TextField('Заметки', blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Пациент'
        verbose_name_plural = 'Пациенты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Пациент: {self.user.get_full_name()}'
