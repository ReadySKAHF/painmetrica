"""
Management command: загружает тест NCS-R.

Запуск:
    python manage.py load_ncsr_test
    python manage.py load_ncsr_test --force  # пересоздать, даже если уже есть
"""
from django.core.management.base import BaseCommand

from tests.models import Question, QuestionOption, ScoreRange, Stage, Test


TEST_TITLE = 'Тест NCS-R'

STAGE = (
    1, 1,
    'Тест NCS-R',
    'Пересмотренная шкала ноцицептивной комы',
    'Пересмотренная шкала ноцицептивной комы (NCS-R)',
    'Детальная оценка различных аспектов нейропатической боли по 11-балльной шкале '
    'для точного описания характера болевых ощущений. '
    'Используется для пациентов, находящихся в коме',
)

# (block_title, question_text, options: [(text, score), ...], order)
QUESTIONS = [
    (
        '', 'Двигательный ответ',
        [
            ('Движения, соответствующие командам', 3),
            ('Локализация стимула (движение руки к месту стимуляции или выше уровня ключицы)', 2),
            ('Отдергивание (сгибание/разгибание)', 1),
            ('Отсутствие ответа или рефлекторные движения', 0),
        ],
        1,
    ),
    (
        '', 'Словесный ответ',
        [
            ('Произнесение слов/фраз', 3),
            ('Плач/Крик', 2),
            ('Стоны/Вокализации', 1),
            ('Отсутствие словесного ответа', 0),
        ],
        2,
    ),
    (
        '', 'Мимический ответ',
        [
            ('Гримаса боли (нахмуривание бровей, зажмуривание глаз, наморщивание носа)', 2),
            ('Расслабленное выражение лица', 1),
            ('Отсутствие мимики', 0),
        ],
        3,
    ),
]

# (min_score, max_score, label, conclusion, sidebar_step)
SCORE_RANGES = [
    (
        0, 0,
        'Ноцицептивный ответ отсутствует',
        'Отсутствие какого-либо наблюдаемого ноцицептивного ответа.',
        1,
    ),
    (
        1, 2,
        'Слабый ноцицептивный ответ',
        'Может быть неспецифическим или рефлекторным. Требуется наблюдение и повторная оценка боли.',
        1,
    ),
    (
        3, 4,
        'Умеренный ноцицептивный ответ',
        'Рассматривается как клинически значимый показатель вероятной боли/дискомфорта. '
        'Является прямым показанием к оценке текущей анальгезии и, скорее всего, к ее усилению '
        'или введению «скоропомощного» анальгетика перед процедурами.',
        1,
    ),
    (
        5, 8,
        'Выраженный ноцицептивный ответ.',
        'С высокой вероятностью указывает на наличие некупированного болевого синдрома. '
        'Требует немедленной коррекции обезболивающей терапии (болюсное введение анальгетика, '
        'титрация инфузии) и диагностического поиска причины боли (новое повреждение, осложнение).',
        1,
    ),
]


class Command(BaseCommand):
    help = 'Загружает тест NCS-R в базу данных'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Пересоздать тест, если уже существует')

    def handle(self, *args, **options):
        force = options['force']

        if Test.objects.filter(title=TEST_TITLE).exists():
            if not force:
                self.stdout.write(self.style.WARNING(
                    f'Тест «{TEST_TITLE}» уже существует. Используйте --force для пересоздания.'
                ))
                return
            Test.objects.filter(title=TEST_TITLE).delete()
            self.stdout.write(self.style.WARNING(f'Тест «{TEST_TITLE}» удалён для пересоздания.'))

        # Создаём тест
        test = Test.objects.create(
            title=TEST_TITLE,
            description='Пересмотренная шкала ноцицептивной комы для оценки боли у пациентов в коме.',
            category='ncsr',
            is_active=True,
            created_by=None,
        )

        # Создаём этап
        order, sidebar_step, name, description, page_title, annotation = STAGE
        stage = Stage.objects.create(
            test=test,
            order=order,
            sidebar_step=sidebar_step,
            name=name,
            description=description,
            page_title=page_title,
            annotation=annotation,
        )

        # Создаём вопросы и варианты ответов
        for block_title, question_text, options, q_order in QUESTIONS:
            question = Question.objects.create(
                stage=stage,
                block_title=block_title,
                question_text=question_text,
                question_type='single',
                order=q_order,
                is_required=True,
            )
            for opt_order, (option_text, score) in enumerate(options):
                QuestionOption.objects.create(
                    question=question,
                    option_text=option_text,
                    order=opt_order,
                    score=score,
                )

        # Создаём диапазоны баллов
        for min_score, max_score, label, conclusion, sb_step in SCORE_RANGES:
            ScoreRange.objects.create(
                test=test,
                sidebar_step=sb_step,
                min_score=min_score,
                max_score=max_score,
                label=label,
                conclusion=conclusion,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Тест «{TEST_TITLE}» успешно создан (id={test.pk}): '
            f'1 этап, {len(QUESTIONS)} вопроса, {len(SCORE_RANGES)} диапазона баллов.'
        ))
