from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0002_stage_session'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='test',
            name='instructions',
        ),
    ]
