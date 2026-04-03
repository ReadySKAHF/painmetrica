from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('medications', '0004_remove_notes_add_medicationnote'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='medication',
            name='image',
        ),
    ]
