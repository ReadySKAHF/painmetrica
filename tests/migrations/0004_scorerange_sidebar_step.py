from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0003_remove_test_instructions'),
    ]

    operations = [
        migrations.AddField(
            model_name='scorerange',
            name='sidebar_step',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Шаг сайдбара',
                help_text='К баллам какого шага сайдбара применяется. Пусто = общая сумма.',
            ),
        ),
    ]
