from django.db import migrations


def fix_painad_category(apps, schema_editor):
    Test = apps.get_model('tests', 'Test')
    Test.objects.filter(title__icontains='PAINAD', category='').update(category='painad')


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0009_hads_split_stages'),
    ]

    operations = [
        migrations.RunPython(fix_painad_category, migrations.RunPython.noop),
    ]
