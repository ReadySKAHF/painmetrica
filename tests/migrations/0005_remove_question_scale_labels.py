from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0004_scorerange_sidebar_step'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='question',
            name='scale_min_label',
        ),
        migrations.RemoveField(
            model_name='question',
            name='scale_max_label',
        ),
    ]
