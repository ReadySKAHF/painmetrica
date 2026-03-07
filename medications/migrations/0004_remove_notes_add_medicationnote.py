import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0003_medication_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='medication',
            name='notes',
        ),
        migrations.CreateModel(
            name='MedicationNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(verbose_name='Примечание')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('doctor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='medication_notes',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Врач',
                )),
                ('medication', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='doctor_notes',
                    to='medications.medication',
                    verbose_name='Лекарство',
                )),
            ],
            options={
                'verbose_name': 'Примечание к лекарству',
                'verbose_name_plural': 'Примечания к лекарствам',
                'unique_together': {('medication', 'doctor')},
            },
        ),
    ]
