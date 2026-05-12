from django.db import migrations

VAS_DOCTOR = (
    'Оцените интенсивность боли пациента прямо сейчас, переместив ползунок по шкале '
    'от 0 до 10, где 0 – боли нет совсем, а 10 – сильная боль.'
)
VAS_PATIENT = (
    'Оцените интенсивность вашей боли прямо сейчас, переместив ползунок по шкале '
    'от 0 до 10, где 0 – боли нет совсем, а 10 – сильная боль.'
)

DN4_DOCTOR = (
    'Ответьте на вопросы о характере боли пациента. Тест помогает определить, имеет ли '
    'боль нейропатическую природу (связана ли с поражением нервов). Тест состоит из двух частей.'
)
DN4_PATIENT = (
    'Ответьте на вопросы о характере вашей боли. Тест помогает определить, имеет ли '
    'боль нейропатическую природу (связана ли с поражением нервов). Тест состоит из двух частей.'
)

HADS_DOCTOR = (
    'Оцените эмоциональное состояние пациента за последнюю неделю. Тест выявляет признаки '
    'тревоги и депрессии, которые часто сопровождают хроническую боль. Тест состоит из двух частей.'
)
HADS_PATIENT = (
    'Оцените своё эмоциональное состояние за последнюю неделю. Тест выявляет признаки '
    'тревоги и депрессии, которые часто сопровождают хроническую боль. Тест состоит из двух частей.'
)


def populate(apps, schema_editor):
    Stage = apps.get_model('tests', 'Stage')
    Test = apps.get_model('tests', 'Test')

    try:
        main_test = Test.objects.get(title='Комплексная оценка болевого синдрома')
    except Test.DoesNotExist:
        return

    stages = Stage.objects.filter(test=main_test)

    # VAS — order=1
    stages.filter(order=1).update(
        annotation_doctor=VAS_DOCTOR,
        annotation_patient=VAS_PATIENT,
    )
    # DN4 — order=2,3
    stages.filter(order__in=[2, 3]).update(
        annotation_doctor=DN4_DOCTOR,
        annotation_patient=DN4_PATIENT,
    )
    # HADS тревога и депрессия — order=5,6
    stages.filter(order__in=[5, 6]).update(
        annotation_doctor=HADS_DOCTOR,
        annotation_patient=HADS_PATIENT,
    )


def reverse_populate(apps, schema_editor):
    Stage = apps.get_model('tests', 'Stage')
    Stage.objects.all().update(annotation_doctor='', annotation_patient='')


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0013_add_role_annotations_to_stage'),
    ]

    operations = [
        migrations.RunPython(populate, reverse_populate),
    ]
