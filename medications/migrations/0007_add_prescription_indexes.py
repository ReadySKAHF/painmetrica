from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0006_add_label_to_medication'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='prescription',
            index=models.Index(
                fields=['patient', 'is_active', '-created_at'],
                name='prescription_patient_active_idx'
            ),
        ),
    ]
