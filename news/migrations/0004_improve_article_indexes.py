from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0003_add_status_index'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='article',
            index=models.Index(
                fields=['status', '-date'],
                name='article_status_date_idx'
            ),
        ),
    ]
