import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Загружает все локальные медиафайлы в Supabase Storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет загружено без реальной загрузки',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        media_root = Path(settings.BASE_DIR) / 'media'

        if not media_root.exists():
            self.stdout.write(self.style.ERROR(f'Папка media не найдена: {media_root}'))
            return

        files = [p for p in media_root.rglob('*') if p.is_file()]

        if not files:
            self.stdout.write(self.style.WARNING('Нет файлов для загрузки'))
            return

        self.stdout.write(f'Найдено файлов: {len(files)}')
        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN, файлы не загружаются ---'))

        uploaded = 0
        skipped = 0
        errors = 0

        for file_path in files:
            # Относительный путь внутри media/ (например: medications/ibufen.png)
            relative = file_path.relative_to(media_root).as_posix()

            try:
                if default_storage.exists(relative):
                    self.stdout.write(f'  пропущен (уже есть): {relative}')
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  [dry-run] загрузить: {relative}')
                    uploaded += 1
                    continue

                with open(file_path, 'rb') as f:
                    default_storage.save(relative, f)

                self.stdout.write(self.style.SUCCESS(f'  загружен: {relative}'))
                uploaded += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ошибка {relative}: {e}'))
                errors += 1

        self.stdout.write('')
        self.stdout.write(f'Загружено: {uploaded}  |  Пропущено: {skipped}  |  Ошибок: {errors}')
