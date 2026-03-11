import uuid

from django.db import models
from django.conf import settings


class Test(models.Model):
    """Модель теста/опросника (батарея из нескольких этапов)"""

    title = models.CharField('Название', max_length=300)
    description = models.TextField('Описание')
    is_active = models.BooleanField('Активен', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='created_tests',
        verbose_name='Создал',
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Тест'
        verbose_name_plural = 'Тесты'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Stage(models.Model):
    """Этап теста — одна страница в пошаговом прохождении.
    DN4 занимает 2 этапа (order=2 и order=3), но sidebar_step=2 у обоих,
    поэтому в сайдбаре они отображаются как один шаг."""

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='stages',
        verbose_name='Тест',
    )
    name = models.CharField('Название (сайдбар)', max_length=100)
    description = models.CharField('Описание (сайдбар)', max_length=200)
    page_title = models.CharField('Заголовок страницы', max_length=200)
    annotation = models.TextField('Аннотация (синий баннер)', blank=True)
    order = models.PositiveIntegerField('Порядок страниц', default=1)
    sidebar_step = models.PositiveIntegerField(
        'Шаг в сайдбаре', default=1,
        help_text='DN4 часть 1 и часть 2 имеют один sidebar_step=2'
    )

    class Meta:
        verbose_name = 'Этап'
        verbose_name_plural = 'Этапы'
        ordering = ['test', 'order']

    def __str__(self):
        return f'{self.test.title} — {self.page_title}'


class Question(models.Model):
    """Вопрос теста, привязан к этапу"""

    QUESTION_TYPE_CHOICES = [
        ('scale', 'Шкала (ползунок)'),
        ('single', 'Одиночный выбор'),
        ('multiple', 'Множественный выбор'),
    ]

    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Этап',
        null=True,
        blank=True,
    )
    block_title = models.CharField(
        'Заголовок блока вопросов', max_length=300, blank=True,
        help_text='Подзаголовок группы вопросов, например «Соответствует ли боль...»'
    )
    question_text = models.TextField('Текст вопроса')
    question_type = models.CharField('Тип вопроса', max_length=20, choices=QUESTION_TYPE_CHOICES)
    order = models.PositiveIntegerField('Порядок', default=0)

    # Для ползунка (scale)
    scale_min = models.IntegerField('Минимум шкалы', null=True, blank=True)
    scale_max = models.IntegerField('Максимум шкалы', null=True, blank=True)
    scale_labels = models.JSONField(
        'Подписи шкалы', default=list, blank=True,
        help_text='Пример: [{"min":0,"max":1,"label":"Нет боли"},{"min":2,"max":3,"label":"Лёгкая боль"}]'
    )

    is_required = models.BooleanField('Обязательный', default=True)

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['stage', 'order']

    def __str__(self):
        stage_title = self.stage.page_title if self.stage else '—'
        return f'{stage_title}: {self.question_text[:60]}'


class QuestionOption(models.Model):
    """Вариант ответа с весом (баллами)"""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name='Вопрос',
    )
    option_text = models.CharField('Текст варианта', max_length=300)
    order = models.PositiveIntegerField('Порядок', default=0)
    score = models.IntegerField('Баллы (вес)', default=0)

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['question', 'order']

    def __str__(self):
        return f'{self.option_text} ({self.score} б.)'


class ScoreRange(models.Model):
    """Диапазон баллов → автоматическое заключение.
    sidebar_step указывает, к баллам какого шага сайдбара применяется диапазон.
    Например, sidebar_step=2 — суммарный балл DN4 (этапы 2 и 3 вместе)."""

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='score_ranges',
        verbose_name='Тест',
    )
    sidebar_step = models.PositiveIntegerField(
        'Шаг сайдбара', null=True, blank=True,
        help_text='К баллам какого шага сайдбара применяется (1=VAS, 2=DN4, 3=CSI, 4=HADS). '
                  'Пусто = применяется к общей сумме всего теста.',
    )
    min_score = models.IntegerField('Минимум баллов')
    max_score = models.IntegerField('Максимум баллов')
    label = models.CharField('Краткое заключение', max_length=200)
    conclusion = models.TextField('Полное заключение')

    class Meta:
        verbose_name = 'Диапазон баллов'
        verbose_name_plural = 'Диапазоны баллов'
        ordering = ['test', 'min_score']

    def __str__(self):
        return f'{self.test.title}: {self.min_score}–{self.max_score} → {self.label}'


class TestSession(models.Model):
    """Сессия прохождения теста.
    UUID в URL делает ссылку непредсказуемой без дополнительного шифрования."""

    STATUS_CHOICES = [
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='Тест',
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='test_sessions',
        verbose_name='Пациент',
    )
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_sessions',
        verbose_name='Проводил тест',
        help_text='Если доктор заполняет за пациента — здесь доктор, иначе сам пациент',
    )
    current_stage_order = models.PositiveIntegerField('Текущий этап (порядок)', default=1)
    answers_data = models.JSONField(
        'Промежуточные ответы', default=dict,
        help_text='{"q_<id>": value} — сохраняется при каждом переходе'
    )
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='in_progress')
    started_at = models.DateTimeField('Начато', auto_now_add=True)
    completed_at = models.DateTimeField('Завершено', null=True, blank=True)

    class Meta:
        verbose_name = 'Сессия тестирования'
        verbose_name_plural = 'Сессии тестирования'
        ordering = ['-started_at']

    def __str__(self):
        return f'Сессия {self.patient} — {self.test.title} [{self.status}]'


class TestResult(models.Model):
    """Итоговый результат завершённой сессии"""

    STATUS_CHOICES = [
        ('completed', 'Завершён'),
        ('reviewed', 'Проверен врачом'),
    ]

    session = models.OneToOneField(
        TestSession,
        on_delete=models.CASCADE,
        related_name='result',
        verbose_name='Сессия',
        null=True,
        blank=True,
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='Тест',
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='test_results',
        verbose_name='Пациент',
    )
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_results',
        verbose_name='Проводил тест',
    )
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='completed')
    total_score = models.IntegerField('Общий балл', default=0)
    conclusion_label = models.CharField('Краткое заключение', max_length=200, blank=True)
    conclusion_text = models.TextField('Полное заключение', blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'user_type': 'doctor'},
        related_name='reviewed_results',
        verbose_name='Проверил',
    )
    doctor_notes = models.TextField('Заметки врача', blank=True)

    started_at = models.DateTimeField('Начато', null=True, blank=True)
    completed_at = models.DateTimeField('Завершено', null=True, blank=True)
    reviewed_at = models.DateTimeField('Проверено', null=True, blank=True)

    class Meta:
        verbose_name = 'Результат теста'
        verbose_name_plural = 'Результаты тестов'
        ordering = ['-completed_at']

    def __str__(self):
        return f'{self.test.title} — {self.patient.user.get_full_name()} ({self.total_score} б.)'


class Answer(models.Model):
    """Ответ на один вопрос в рамках TestResult"""

    result = models.ForeignKey(
        TestResult,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Результат',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос',
    )
    selected_options = models.ManyToManyField(
        QuestionOption,
        blank=True,
        related_name='answers',
        verbose_name='Выбранные варианты',
    )
    scale_value = models.IntegerField('Значение шкалы', null=True, blank=True)
    score = models.IntegerField('Баллы', default=0)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        unique_together = ['result', 'question']

    def __str__(self):
        return f'Ответ [{self.score} б.] на: {self.question.question_text[:50]}'
