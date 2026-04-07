import openpyxl
from django.core.management.base import BaseCommand
from therapy.models import Therapy


class Command(BaseCommand):
    help = 'Импорт реабилитационных мероприятий из XLSX-файла'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', type=str, help='Путь к файлу .xlsx')

    def handle(self, *args, **options):
        path = options['xlsx_path']
        wb = openpyxl.load_workbook(path)
        ws = wb.active

        created = 0
        skipped = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            name, therapy_type, prescription_scheme, clinical_goal = row

            if not name:
                continue

            _, was_created = Therapy.objects.get_or_create(
                name=name,
                defaults={
                    'therapy_type': therapy_type or '',
                    'prescription_scheme': prescription_scheme or '',
                    'clinical_goal': clinical_goal or '',
                }
            )

            if was_created:
                created += 1
                self.stdout.write(f'  + {name}')
            else:
                skipped += 1
                self.stdout.write(f'  ~ уже существует: {name}')

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово: создано {created}, пропущено {skipped}.'
        ))
