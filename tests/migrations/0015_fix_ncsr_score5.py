from django.db import migrations


UMEREN_CONCLUSION = (
    'Рассматривается как клинически значимый показатель вероятной боли/дискомфорта. '
    'Является прямым показанием к оценке текущей анальгезии и, скорее всего, к ее усилению '
    'или введению «скоропомощного» анальгетика перед процедурами.'
)

VYRAZHEN_CONCLUSION = (
    'С высокой вероятностью указывает на наличие некупированного болевого синдрома. '
    'Требует немедленной коррекции обезболивающей терапии (болюсное введение анальгетика, '
    'титрация инфузии) и диагностического поиска причины боли (новое повреждение, осложнение).'
)


def fix_ncsr_score5(apps, schema_editor):
    Test = apps.get_model('tests', 'Test')
    ScoreRange = apps.get_model('tests', 'ScoreRange')

    test = Test.objects.filter(category='ncsr').first()
    if not test:
        return

    # Удаляем все диапазоны NCS-R начиная с 3 баллов (Умеренный и Выраженный)
    # и пересоздаём с правильными границами и текстами
    ScoreRange.objects.filter(test=test, sidebar_step=1, min_score__gte=3).delete()

    ScoreRange.objects.create(
        test=test,
        sidebar_step=1,
        min_score=3,
        max_score=4,
        label='Умеренный ноцицептивный ответ',
        conclusion=UMEREN_CONCLUSION,
    )
    ScoreRange.objects.create(
        test=test,
        sidebar_step=1,
        min_score=5,
        max_score=8,
        label='Выраженный ноцицептивный ответ',
        conclusion=VYRAZHEN_CONCLUSION,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0014_populate_role_annotations'),
    ]

    operations = [
        migrations.RunPython(fix_ncsr_score5, migrations.RunPython.noop),
    ]
