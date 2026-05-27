from django.db import migrations


def fix_ncsr_ranges(apps, schema_editor):
    ScoreRange = apps.get_model('tests', 'ScoreRange')
    Test = apps.get_model('tests', 'Test')

    test = Test.objects.filter(category='ncsr').first()
    if not test:
        return

    # Диапазон 0–0: был label = длинный текст, conclusion = ""
    ScoreRange.objects.filter(test=test, min_score=0, max_score=0).update(
        label='Ноцицептивный ответ отсутствует',
        conclusion='Отсутствие какого-либо наблюдаемого ноцицептивного ответа.',
    )

    # Диапазон 5–8: добавляем точку к label
    ScoreRange.objects.filter(test=test, min_score=5, max_score=8).update(
        label='Выраженный ноцицептивный ответ.',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0017_fix_painad_score_ranges'),
    ]

    operations = [
        migrations.RunPython(fix_ncsr_ranges, migrations.RunPython.noop),
    ]
