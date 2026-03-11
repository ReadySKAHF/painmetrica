import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0001_initial'),
        ('patients', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Создаём Stage
        migrations.CreateModel(
            name='Stage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название (сайдбар)')),
                ('description', models.CharField(max_length=200, verbose_name='Описание (сайдбар)')),
                ('page_title', models.CharField(max_length=200, verbose_name='Заголовок страницы')),
                ('annotation', models.TextField(blank=True, verbose_name='Аннотация (синий баннер)')),
                ('order', models.PositiveIntegerField(default=1, verbose_name='Порядок страниц')),
                ('sidebar_step', models.PositiveIntegerField(default=1, help_text='DN4 часть 1 и часть 2 имеют один sidebar_step=2', verbose_name='Шаг в сайдбаре')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stages', to='tests.test', verbose_name='Тест')),
            ],
            options={
                'verbose_name': 'Этап',
                'verbose_name_plural': 'Этапы',
                'ordering': ['test', 'order'],
            },
        ),

        # 2. Добавляем stage (nullable) к Question
        migrations.AddField(
            model_name='question',
            name='stage',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='questions',
                to='tests.stage',
                verbose_name='Этап',
            ),
        ),

        # 3. block_title к Question
        migrations.AddField(
            model_name='question',
            name='block_title',
            field=models.CharField(
                blank=True, max_length=300,
                verbose_name='Заголовок блока вопросов',
                help_text='Подзаголовок группы вопросов, например «Соответствует ли боль...»',
            ),
        ),

        # 4. scale_labels к Question
        migrations.AddField(
            model_name='question',
            name='scale_labels',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Подписи шкалы',
                help_text='Пример: [{"min":0,"max":1,"label":"Нет боли"}]',
            ),
        ),

        # 5. Удаляем старый ForeignKey test у Question
        migrations.RemoveField(
            model_name='question',
            name='test',
        ),

        # 6. Создаём ScoreRange
        migrations.CreateModel(
            name='ScoreRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_score', models.IntegerField(verbose_name='Минимум баллов')),
                ('max_score', models.IntegerField(verbose_name='Максимум баллов')),
                ('label', models.CharField(max_length=200, verbose_name='Краткое заключение')),
                ('conclusion', models.TextField(verbose_name='Полное заключение')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='score_ranges', to='tests.test', verbose_name='Тест')),
            ],
            options={
                'verbose_name': 'Диапазон баллов',
                'verbose_name_plural': 'Диапазоны баллов',
                'ordering': ['test', 'min_score'],
            },
        ),

        # 7. Создаём TestSession
        migrations.CreateModel(
            name='TestSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('current_stage_order', models.PositiveIntegerField(default=1, verbose_name='Текущий этап (порядок)')),
                ('answers_data', models.JSONField(default=dict, verbose_name='Промежуточные ответы')),
                ('status', models.CharField(
                    choices=[('in_progress', 'В процессе'), ('completed', 'Завершена')],
                    default='in_progress', max_length=20, verbose_name='Статус',
                )),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='Начато')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Завершено')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_sessions', to='patients.patient', verbose_name='Пациент')),
                ('taken_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='conducted_sessions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Проводил тест',
                )),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='tests.test', verbose_name='Тест')),
            ],
            options={
                'verbose_name': 'Сессия тестирования',
                'verbose_name_plural': 'Сессии тестирования',
                'ordering': ['-started_at'],
            },
        ),

        # 8. Добавляем session к TestResult
        migrations.AddField(
            model_name='testresult',
            name='session',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='result',
                to='tests.testsession',
                verbose_name='Сессия',
            ),
        ),

        # 9. Добавляем taken_by к TestResult
        migrations.AddField(
            model_name='testresult',
            name='taken_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='conducted_results',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Проводил тест',
            ),
        ),

        # 10. Добавляем поля заключения к TestResult
        migrations.AddField(
            model_name='testresult',
            name='conclusion_label',
            field=models.CharField(blank=True, max_length=200, verbose_name='Краткое заключение'),
        ),
        migrations.AddField(
            model_name='testresult',
            name='conclusion_text',
            field=models.TextField(blank=True, verbose_name='Полное заключение'),
        ),

        # 11. started_at в TestResult делаем nullable (теперь копируется из сессии)
        migrations.AlterField(
            model_name='testresult',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Начато'),
        ),

        # 12. Удаляем text_answer из Answer (не используется в новом флоу)
        migrations.RemoveField(
            model_name='answer',
            name='text_answer',
        ),
    ]
