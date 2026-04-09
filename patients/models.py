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


class Conclusion(models.Model):
    """Итоговое консультативное заключение по пациенту"""

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='conclusions',
        verbose_name='Пациент',
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'user_type': 'doctor'},
        related_name='created_conclusions',
        verbose_name='Врач',
    )
    last_test_result = models.ForeignKey(
        'tests.TestResult',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conclusions',
        verbose_name='Последний результат теста',
    )
    medications = models.ManyToManyField(
        'medications.Medication',
        through='ConclusionMedication',
        verbose_name='Лекарства',
        blank=True,
    )
    therapies = models.ManyToManyField(
        'therapy.Therapy',
        through='ConclusionTherapy',
        verbose_name='Реабилитационные мероприятия',
        blank=True,
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Заключение'
        verbose_name_plural = 'Заключения'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заключение для {self.patient} от {self.created_at.strftime("%d.%m.%Y")}'


class ConclusionMedication(models.Model):
    """Лекарство в заключении"""

    conclusion = models.ForeignKey(
        Conclusion,
        on_delete=models.CASCADE,
        related_name='conclusion_medications',
        verbose_name='Заключение',
    )
    medication = models.ForeignKey(
        'medications.Medication',
        on_delete=models.CASCADE,
        related_name='in_conclusions',
        verbose_name='Лекарство',
    )

    class Meta:
        verbose_name = 'Лекарство в заключении'
        verbose_name_plural = 'Лекарства в заключениях'
        unique_together = [['conclusion', 'medication']]


class ConclusionTherapy(models.Model):
    """Реабилитационное мероприятие в заключении"""

    conclusion = models.ForeignKey(
        Conclusion,
        on_delete=models.CASCADE,
        related_name='conclusion_therapies',
        verbose_name='Заключение',
    )
    therapy = models.ForeignKey(
        'therapy.Therapy',
        on_delete=models.CASCADE,
        related_name='in_conclusions',
        verbose_name='Терапия',
    )

    class Meta:
        verbose_name = 'Мероприятие в заключении'
        verbose_name_plural = 'Мероприятия в заключениях'
        unique_together = [['conclusion', 'therapy']]
