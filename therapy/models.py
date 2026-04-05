from django.db import models
from django.conf import settings


class Therapy(models.Model):
    """Реабилитационная терапия"""

    name = models.CharField('Название', max_length=200)
    therapy_type = models.CharField('Тип', max_length=100, blank=True)
    prescription_scheme = models.TextField('Схема назначения', blank=True)
    clinical_goal = models.TextField('Клиническая цель', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='created_therapies',
        verbose_name='Создал'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Терапия'
        verbose_name_plural = 'Терапии'
        ordering = ['name']

    def __str__(self):
        return self.name


class TherapyNote(models.Model):
    """Примечание врача к терапии — у каждого доктора своё"""

    therapy = models.ForeignKey(
        Therapy,
        on_delete=models.CASCADE,
        related_name='doctor_notes',
        verbose_name='Терапия'
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='therapy_notes',
        verbose_name='Врач'
    )
    text = models.TextField('Примечание')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Примечание к терапии'
        verbose_name_plural = 'Примечания к терапиям'
        unique_together = [['therapy', 'doctor']]

    def __str__(self):
        return f'Примечание {self.doctor} к {self.therapy}'
