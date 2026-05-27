from django.db import migrations


PAINAD_RANGES = [
    (0,  0,  'Боль отсутствует',                         'Лечение не требуется'),
    (1,  3,  'Слабый по интенсивности болевой синдром',  ''),
    (4,  6,  'Средний по интенсивности болевой синдром', ''),
    (7,  10, 'Сильный по интенсивности болевой синдром', ''),
]


def fix_painad_ranges(apps, schema_editor):
    ScoreRange = apps.get_model('tests', 'ScoreRange')
    Test = apps.get_model('tests', 'Test')

    try:
        test = Test.objects.get(category='painad')
    except Test.DoesNotExist:
        return

    for min_score, max_score, label, conclusion in PAINAD_RANGES:
        ScoreRange.objects.filter(
            test=test, min_score=min_score, max_score=max_score,
        ).update(label=label, conclusion=conclusion)


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0016_update_vas_scale_labels'),
    ]

    operations = [
        migrations.RunPython(fix_painad_ranges, migrations.RunPython.noop),
    ]
