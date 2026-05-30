from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_add_otp_indexes'),
    ]

    operations = [
        # Удаляем индекс по полю code перед его удалением (если есть)
        migrations.RemoveField(
            model_name='otpcode',
            name='code',
        ),
        migrations.AddField(
            model_name='otpcode',
            name='code_hash',
            field=models.CharField(default='', max_length=64, verbose_name='Хеш OTP кода'),
            preserve_default=False,
        ),
    ]
