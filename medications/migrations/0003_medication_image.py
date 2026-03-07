from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0002_update_medication_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='medication',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='medications/', verbose_name='Фото'),
        ),
    ]
