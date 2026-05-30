from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0006_add_archival_fields_to_patient'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(
                fields=['assigned_doctor', '-created_at'],
                name='patient_doctor_date_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(
                fields=['is_archived'],
                name='patient_archived_idx'
            ),
        ),
    ]
