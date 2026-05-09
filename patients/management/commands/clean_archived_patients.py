from django.core.management.base import BaseCommand
from django.utils import timezone

from patients.models import Patient


class Command(BaseCommand):
    help = (
        'Физически удаляет архивированные записи пациентов, '
        'у которых истёк срок хранения (scheduled_deletion_at <= now).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет удалено, без реального удаления.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        qs = Patient.objects.filter(
            is_archived=True,
            scheduled_deletion_at__lte=now,
        )
        count = qs.count()

        if count == 0:
            self.stdout.write('Нет записей, готовых к удалению.')
            return

        if options['dry-run']:
            self.stdout.write(f'[dry-run] Будет удалено {count} записей пациентов:')
            for p in qs:
                self.stdout.write(f'  pk={p.pk}, archived_at={p.archived_at}, scheduled_deletion_at={p.scheduled_deletion_at}')
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено архивированных записей пациентов: {count}'))
