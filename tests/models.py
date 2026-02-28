from django.db import models
from django.conf import settings


class Test(models.Model):
    """Модель теста/опросника для пациентов"""

    title = models.CharField('Название', max_length=300)
    description = models.TextField('Описание')
    instructions = models.TextField('Инструкции', blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='created_tests',
        verbose_name='Создал'
    )

    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Question(models.Model):
    """Модель вопроса теста"""

    QUESTION_TYPE_CHOICES = [
        ('text', 'Текстовый ответ'),
        ('single', 'Одиночный выбор'),
        ('multiple', 'Множественный выбор'),
        ('scale', 'Шкала'),
    ]

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Тест'
    )
    question_text = models.TextField('Текст вопроса')
    question_type = models.CharField('Тип вопроса', max_length=20, choices=QUESTION_TYPE_CHOICES)
    order = models.PositiveIntegerField('Порядок', default=0)

    # Для шкал
    scale_min = models.IntegerField('Минимум шкалы', null=True, blank=True)
    scale_max = models.IntegerField('Максимум шкалы', null=True, blank=True)
    scale_min_label = models.CharField('Подпись минимума', max_length=100, blank=True)
    scale_max_label = models.CharField('Подпись максимума', max_length=100, blank=True)

    is_required = models.BooleanField('Обязательный', default=True)

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['test', 'order']

    def __str__(self):
        return f'{self.test.title}: {self.question_text[:50]}'


class QuestionOption(models.Model):
    """Варианты ответов для вопросов с выбором"""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name='Вопрос'
    )
    option_text = models.CharField('Текст варианта', max_length=300)
    order = models.PositiveIntegerField('Порядок', default=0)
    score = models.IntegerField('Баллы', default=0)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['question', 'order']

    def __str__(self):
        return self.option_text


class TestResult(models.Model):
    """Результат прохождения теста пациентом"""

    STATUS_CHOICES = [
        ('in_progress', 'В процессе'),
        ('completed', 'Завершен'),
        ('reviewed', 'Проверен'),
    ]

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Тест'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='test_results',
        verbose_name='Пациент'
    )

    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='in_progress')
    total_score = models.IntegerField('Общий балл', default=0)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='reviewed_results',
        verbose_name='Проверил'
    )
    doctor_notes = models.TextField('Заметки врача', blank=True)

    started_at = models.DateTimeField('Начато', auto_now_add=True)
    completed_at = models.DateTimeField('Завершено', null=True, blank=True)
    reviewed_at = models.DateTimeField('Проверено', null=True, blank=True)

    class Meta:
        verbose_name = 'Результат теста'
        verbose_name_plural = 'Результаты тестов'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.test.title} - {self.patient.user.get_full_name()} ({self.status})'


class Answer(models.Model):
    """Ответ пациента на вопрос"""

    result = models.ForeignKey(
        TestResult,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Результат'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос'
    )

    # Разные типы ответов
    text_answer = models.TextField('Текстовый ответ', blank=True)
    selected_options = models.ManyToManyField(
        QuestionOption,
        blank=True,
        related_name='answers',
        verbose_name='Выбранные варианты'
    )
    scale_value = models.IntegerField('Значение шкалы', null=True, blank=True)

    score = models.IntegerField('Баллы', default=0)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        unique_together = ['result', 'question']

    def __str__(self):
        return f'Ответ на: {self.question.question_text[:50]}'
