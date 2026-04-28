from django.db import migrations


def fix_ncsr_labels(apps, schema_editor):
    ScoreRange = apps.get_model('tests', 'ScoreRange')
    labels_to_fix = [
        'Слабый ноцицептивный ответ.',
        'Умеренный ноцицептивный ответ.',
        'Выраженный ноцицептивный ответ.',
    ]
    for label in labels_to_fix:
        ScoreRange.objects.filter(label=label).update(label=label.rstrip('.'))


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0010_fix_painad_category'),
    ]

    operations = [
        migrations.RunPython(fix_ncsr_labels, migrations.RunPython.noop),
    ]
