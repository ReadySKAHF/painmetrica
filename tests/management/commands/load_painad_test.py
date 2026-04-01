"""
Management command: загружает тест PAINAD.

Запуск:
    python manage.py load_painad_test
    python manage.py load_painad_test --force  # пересоздать, даже если уже есть
"""
from django.core.management.base import BaseCommand

from tests.models import Question, QuestionOption, ScoreRange, Stage, Test


TEST_TITLE = 'Тест PAINAD'

STAGE = (
    1, 1,
    'Тест PAINAD',
    'Шкала для оценки боли',
    'Тест PAINAD',
    'Шкала для оценки боли у пациентов с деменцией и когнитивными нарушениями, '
    'которые не могут самостоятельно описать свои ощущения. '
    'Определяется реакция человека на раздражители.',
)

# (block_title, question_text, options: [(text, score), ...], order)
QUESTIONS = [
    (
        '', 'Дыхание',
        [
            ('У человека нормальное дыхание', 0),
            ('У человека иногда затрудненное дыхание, краткий период гипервентиляции', 1),
            ('У человека громкое затрудненное дыхание, длинный период гипервентиляции, Чейн-Стокса', 2),
        ],
        1,
    ),
    (
        '', 'Неприятные звуки',
        [
            ('У человека отсутствует реакция', 0),
            ('У человека одиночный вздох или стон; тихий голос, негативное или неодобрительное содержание речи', 1),
            ('У человека повторяющиеся крики, громкие вздохи или стоны, плач', 2),
        ],
        2,
    ),
    (
        '', 'Выражение лица',
        [
            ('У человека улыбка или ничего не выражающее выражение лица', 0),
            ('У человека печальное, испуганное, хмурое выражение лица', 1),
            ('Человек морщится', 2),
        ],
        3,
    ),
    (
        '', 'Поза и жесты',
        [
            ('Человек расслаблен', 0),
            ('Человек напряжен, ерзает, но малоподвижен', 1),
            ('Человек скован, сжатые кулаки, согнутые колени, отталкивает проверяющего, дерется', 2),
        ],
        4,
    ),
    (
        '', 'Возможность утешить',
        [
            ('Человек не нуждается в утешении', 0),
            ('Человека можно отвлечь/утешить голосом или прикосновением', 1),
            ('Человека невозможно успокоить, отвлечь или приободрить', 2),
        ],
        5,
    ),
]

# (min_score, max_score, label, conclusion, sidebar_step)
SCORE_RANGES = [
    (0,  0,  'Боль отсутствует',       'Признаков боли не выявлено.',                                            1),
    (1,  3,  'Слабый по интенсивности болевой синдром',   'Выявлены признаки слабой боли. Рекомендуется наблюдение.',              1),
    (4,  6,  'Средний по интенсивности болевой синдром', 'Выявлена боль средней тяжести. Рекомендуется коррекция терапии.',       1),
    (7,  10, 'Сильный по интенсивности болевой синдром', 'Выявлена сильная боль. Требуется немедленная коррекция обезболивания.', 1),
]


class Command(BaseCommand):
    help = 'Загружает тест PAINAD в базу данных'

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
            description='Шкала для оценки боли у пациентов с деменцией и когнитивными нарушениями.',
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
        for min_score, max_score, label, conclusion, sidebar_step in SCORE_RANGES:
            ScoreRange.objects.create(
                test=test,
                sidebar_step=sidebar_step,
                min_score=min_score,
                max_score=max_score,
                label=label,
                conclusion=conclusion,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Тест «{TEST_TITLE}» успешно создан (id={test.pk}): '
            f'1 этап, {len(QUESTIONS)} вопросов, {len(SCORE_RANGES)} диапазонов баллов.'
        ))
