from django.db import migrations

NEW_VAS_LABELS = [
    {'min': 0,  'max': 0,  'label': 'Нет боли'},
    {'min': 1,  'max': 3,  'label': 'Слабый болевой синдром'},
    {'min': 4,  'max': 6,  'label': 'Умеренный болевой синдром'},
    {'min': 7,  'max': 10, 'label': 'Сильный болевой синдром'},
]


def update_vas_labels(apps, schema_editor):
    Question = apps.get_model('tests', 'Question')
    Question.objects.filter(
        question_type='scale',
        stage__order=1,
        stage__test__title='Комплексная оценка болевого синдрома',
    ).update(scale_labels=NEW_VAS_LABELS)


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0015_fix_ncsr_score5'),
    ]

    operations = [
        migrations.RunPython(update_vas_labels, migrations.RunPython.noop),
    ]
