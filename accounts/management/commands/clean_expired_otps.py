from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import OTPCode


class Command(BaseCommand):
    help = 'Удаляет истёкшие OTP-коды из базы данных'

    def handle(self, *args, **options):
        deleted, _ = OTPCode.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено {deleted} истёкших OTP-кодов'))
