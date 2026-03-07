from django.db import models
from django.conf import settings


class Medication(models.Model):
    """Модель лекарства"""

    name = models.CharField('Название', max_length=200)
    medication_type = models.CharField('Тип', max_length=100, blank=True)
    image = models.ImageField('Фото', upload_to='medications/', blank=True, null=True)
    prescription_scheme = models.TextField('Схема назначения', blank=True)
    side_effects = models.TextField('Побочные эффекты', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='created_medications',
        verbose_name='Создал'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Лекарство'
        verbose_name_plural = 'Лекарства'
        ordering = ['name']

    def __str__(self):
        return self.name


class MedicationNote(models.Model):
    """Примечание врача к лекарству — у каждого доктора своё"""

    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='doctor_notes',
        verbose_name='Лекарство'
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medication_notes',
        verbose_name='Врач'
    )
    text = models.TextField('Примечание')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Примечание к лекарству'
        verbose_name_plural = 'Примечания к лекарствам'
        unique_together = [['medication', 'doctor']]

    def __str__(self):
        return f'Примечание {self.doctor} к {self.medication}'


class Prescription(models.Model):
    """Модель назначения лекарства пациенту"""

    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='prescriptions',
        verbose_name='Пациент'
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='prescriptions',
        verbose_name='Лекарство'
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'doctor'},
        related_name='prescriptions',
        verbose_name='Врач'
    )

    dosage = models.CharField('Дозировка', max_length=100)
    frequency = models.CharField('Частота приема', max_length=200)
    duration = models.CharField('Длительность', max_length=100, blank=True)
    instructions = models.TextField('Инструкции', blank=True)

    start_date = models.DateField('Дата начала', null=True, blank=True)
    end_date = models.DateField('Дата окончания', null=True, blank=True)

    is_active = models.BooleanField('Активно', default=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Назначение'
        verbose_name_plural = 'Назначения'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.medication.name} для {self.patient.user.get_full_name()}'
