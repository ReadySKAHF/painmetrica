"""
Data migration: разделяет HADS на два независимых шага сайдбара.
- Stage тревоги (order=5): name → 'Тест HADS. Оценка уровня тревоги', sidebar_step остаётся 4
- Stage депрессии (order=6): name → 'Тест HADS. Оценка уровня депрессии', sidebar_step → 5
- ScoreRanges для sidebar_step=4 обновляются под тревогу (0–21)
- Добавляются ScoreRanges для sidebar_step=5 (депрессия, 0–21)
"""
from django.db import migrations


HADS_ANXIETY_RANGES = [
    (0,  7,  'Симптомы тревоги отсутствуют',
     'Достоверно выраженных симптомов тревоги не выявлено (0–7 баллов).'),
    (8,  10, 'Субклинически выраженная тревога',
     'Субклинически выраженная тревога (8–10 баллов). '
     'Рекомендуется динамическое наблюдение.'),
    (11, 21, 'Клинически выраженная тревога',
     'Клинически выраженная тревога (11 и более баллов). '
     'Рекомендуется консультация специалиста и коррекция терапии.'),
]

HADS_DEPRESSION_RANGES = [
    (0,  7,  'Симптомы депрессии отсутствуют',
     'Достоверно выраженных симптомов депрессии не выявлено (0–7 баллов).'),
    (8,  10, 'Субклинически выраженная депрессия',
     'Субклинически выраженная депрессия (8–10 баллов). '
     'Рекомендуется динамическое наблюдение.'),
    (11, 21, 'Клинически выраженная депрессия',
     'Клинически выраженная депрессия (11 и более баллов). '
     'Рекомендуется консультация специалиста и коррекция терапии.'),
]

TEST_TITLE = 'Комплексная оценка болевого синдрома'


def split_hads(apps, schema_editor):
    Test = apps.get_model('tests', 'Test')
    Stage = apps.get_model('tests', 'Stage')
    ScoreRange = apps.get_model('tests', 'ScoreRange')

    try:
        test = Test.objects.get(title=TEST_TITLE)
    except Test.DoesNotExist:
        return

    # Обновляем этапы HADS
    Stage.objects.filter(test=test, order=5).update(
        name='Тест HADS. Оценка уровня тревоги',
    )
    Stage.objects.filter(test=test, order=6).update(
        name='Тест HADS. Оценка уровня депрессии',
        sidebar_step=5,
    )

    # Удаляем старые диапазоны HADS (sidebar_step=4)
    ScoreRange.objects.filter(test=test, sidebar_step=4).delete()

    # Создаём новые диапазоны для тревоги (sidebar_step=4)
    for min_s, max_s, label, conclusion in HADS_ANXIETY_RANGES:
        ScoreRange.objects.create(
            test=test,
            sidebar_step=4,
            min_score=min_s,
            max_score=max_s,
            label=label,
            conclusion=conclusion,
        )

    # Создаём новые диапазоны для депрессии (sidebar_step=5)
    for min_s, max_s, label, conclusion in HADS_DEPRESSION_RANGES:
        ScoreRange.objects.create(
            test=test,
            sidebar_step=5,
            min_score=min_s,
            max_score=max_s,
            label=label,
            conclusion=conclusion,
        )

    # Инвалидируем Redis-кеш чтобы изменения сразу вступили в силу
    try:
        from django.core.cache import cache
        cache.delete(f'score_ranges:{test.pk}')
        cache.delete(f'test_stages:{test.pk}')
    except Exception:
        pass


def reverse_split_hads(apps, schema_editor):
    Test = apps.get_model('tests', 'Test')
    Stage = apps.get_model('tests', 'Stage')
    ScoreRange = apps.get_model('tests', 'ScoreRange')

    try:
        test = Test.objects.get(title=TEST_TITLE)
    except Test.DoesNotExist:
        return

    Stage.objects.filter(test=test, order=5).update(name='Тест HADS')
    Stage.objects.filter(test=test, order=6).update(name='Тест HADS', sidebar_step=4)

    ScoreRange.objects.filter(test=test, sidebar_step__in=[4, 5]).delete()

    ScoreRange.objects.create(
        test=test, sidebar_step=4, min_score=0, max_score=7,
        label='Симптомы тревоги/депрессии отсутствуют',
        conclusion='Достоверно выраженных симптомов тревоги и депрессии не выявлено (0–7 баллов).',
    )
    ScoreRange.objects.create(
        test=test, sidebar_step=4, min_score=8, max_score=10,
        label='Субклинически выраженные симптомы',
        conclusion='Субклинически выраженная тревога/депрессия (8–10 баллов). Рекомендуется динамическое наблюдение.',
    )
    ScoreRange.objects.create(
        test=test, sidebar_step=4, min_score=11, max_score=42,
        label='Клинически выраженные симптомы',
        conclusion='Клинически выраженная тревога/депрессия (11 и более баллов). Рекомендуется консультация психиатра и коррекция терапии.',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0008_add_db_indexes'),
    ]

    operations = [
        migrations.RunPython(split_hads, reverse_code=reverse_split_hads),
    ]
