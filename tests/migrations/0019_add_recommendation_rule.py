from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0001_initial'),
        ('tests', '0018_fix_ncsr_score_ranges'),
        ('therapy', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecommendationRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rule_key', models.SlugField(max_length=60, unique=True, verbose_name='Ключ правила')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Описание')),
                ('medications', models.ManyToManyField(
                    blank=True,
                    related_name='recommendation_rules',
                    to='medications.medication',
                    verbose_name='Лекарства',
                )),
                ('therapies', models.ManyToManyField(
                    blank=True,
                    related_name='recommendation_rules',
                    to='therapy.therapy',
                    verbose_name='Мероприятия',
                )),
            ],
            options={
                'verbose_name': 'Правило рекомендаций',
                'verbose_name_plural': 'Правила рекомендаций',
            },
        ),
    ]
