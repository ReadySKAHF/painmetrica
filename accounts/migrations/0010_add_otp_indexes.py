from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_add_can_manage_news'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='otpcode',
            index=models.Index(
                fields=['user', 'purpose', 'is_used', 'expires_at'],
                name='otpcode_lookup_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='passwordresettoken',
            index=models.Index(
                fields=['user', 'is_used'],
                name='prt_user_used_idx'
            ),
        ),
    ]
