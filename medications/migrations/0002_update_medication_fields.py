from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(model_name='medication', name='description'),
        migrations.RemoveField(model_name='medication', name='dosage_form'),
        migrations.RemoveField(model_name='medication', name='manufacturer'),
        migrations.AddField(
            model_name='medication',
            name='medication_type',
            field=models.CharField(blank=True, max_length=100, verbose_name='Тип'),
        ),
        migrations.AddField(
            model_name='medication',
            name='prescription_scheme',
            field=models.TextField(blank=True, verbose_name='Схема назначения'),
        ),
        migrations.AddField(
            model_name='medication',
            name='side_effects',
            field=models.TextField(blank=True, verbose_name='Побочные эффекты'),
        ),
        migrations.AddField(
            model_name='medication',
            name='notes',
            field=models.CharField(blank=True, max_length=500, verbose_name='Примечания'),
        ),
    ]
