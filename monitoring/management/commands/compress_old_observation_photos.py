import io
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitoring.models import ObservationPhoto

_HEIC_EXTENSIONS = ('.heic', '.heif')
_DEFAULT_OLDER_THAN_DAYS = 180
_DEFAULT_MAX_SIZE_KB = 300
_MAX_DIMENSION = 1600
_JPEG_QUALITY = 80


class Command(BaseCommand):
    help = (
        'Compress full-size ObservationPhoto originals uploaded before a cutoff '
        'to reduce storage. Thumbnails are untouched and photos are never deleted '
        '— only the full-size original is re-encoded at a smaller size/quality.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-days', type=int, default=_DEFAULT_OLDER_THAN_DAYS,
            help=f'Only compress photos uploaded more than this many days ago (default {_DEFAULT_OLDER_THAN_DAYS}).',
        )
        parser.add_argument(
            '--max-size-kb', type=int, default=_DEFAULT_MAX_SIZE_KB,
            help=f'Skip photos already at or below this size in KB (default {_DEFAULT_MAX_SIZE_KB}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be compressed without modifying any files.',
        )

    def handle(self, *args, **options):
        from PIL import Image  # noqa: PLC0415

        cutoff = timezone.now() - timedelta(days=options['older_than_days'])
        max_size_bytes = options['max_size_kb'] * 1024
        dry_run = options['dry_run']

        candidates = ObservationPhoto.objects.filter(uploaded_at__lt=cutoff).exclude(image='')

        compressed = 0
        skipped_small = 0
        skipped_unsupported = 0

        for photo in candidates.iterator():
            if not photo.image or not photo.image.name:
                continue

            if photo.image.name.lower().endswith(_HEIC_EXTENSIONS):
                skipped_unsupported += 1
                continue

            try:
                size = photo.image.size
            except (FileNotFoundError, OSError):
                continue

            if size <= max_size_bytes:
                skipped_small += 1
                continue

            if dry_run:
                self.stdout.write(f'Would compress {photo.image.name} ({size // 1024} KB)')
                compressed += 1
                continue

            try:
                with Image.open(photo.image.path) as img:
                    img_copy = img.copy()
            except Exception:
                skipped_unsupported += 1
                continue

            img_copy.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), Image.Resampling.LANCZOS)
            if img_copy.mode != 'RGB':
                img_copy = img_copy.convert('RGB')
            buf = io.BytesIO()
            img_copy.save(buf, format='JPEG', quality=_JPEG_QUALITY, optimize=True)
            buf.seek(0)

            original_name = photo.image.name
            photo.image.delete(save=False)
            photo.image.save(original_name, ContentFile(buf.read()), save=True)

            new_size = photo.image.size
            self.stdout.write(
                self.style.SUCCESS(
                    f'Compressed {original_name}: {size // 1024} KB -> {new_size // 1024} KB'
                )
            )
            compressed += 1

        self.stdout.write('')
        summary = (
            f'Done. Compressed: {compressed}  '
            f'Skipped (already small): {skipped_small}  '
            f'Skipped (unsupported format): {skipped_unsupported}'
        )
        if dry_run:
            summary += '  [dry run — no files modified]'
        self.stdout.write(self.style.SUCCESS(summary))
