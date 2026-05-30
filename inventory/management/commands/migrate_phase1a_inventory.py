"""
Management command: migrate_phase1a_inventory

Converts existing Phase 1A free-text inventory fields (crop_name,
accession_code, batch_code, location_text) into structured FK models
(Crop, Accession, Batch, Position).

Safe to run multiple times — idempotent.
Does NOT remove or overwrite legacy text fields.
"""
from django.core.management.base import BaseCommand

from inventory.models import (
    Accession, Batch, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)

_DEFAULT_SITE = 'Default Site'
_DEFAULT_SH = 'Unknown Screen House'
_DEFAULT_BENCH = 'Unknown Bench'
_DEFAULT_POS = 'Unspecified'


def _parse_location(text):
    """
    Parse location_text into (screen_house, bench, position_code).

    Handles:
      "SH1 / Bench A"              → ('SH1', 'Bench A', 'Unspecified')
      "SH1 / Bench A / Position 1" → ('SH1', 'Bench A', 'Position 1')
      "Bay 7"                      → (_DEFAULT_SH, 'Bay 7', 'Unspecified')
      ""                           → (_DEFAULT_SH, _DEFAULT_BENCH, 'Unspecified')
    """
    if not text or not text.strip():
        return (_DEFAULT_SH, _DEFAULT_BENCH, _DEFAULT_POS)

    parts = [p.strip() for p in text.split('/') if p.strip()]
    if len(parts) >= 3:
        return (parts[0], parts[1], parts[2])
    if len(parts) == 2:
        return (parts[0], parts[1], _DEFAULT_POS)
    if len(parts) == 1:
        return (_DEFAULT_SH, parts[0], _DEFAULT_POS)
    return (_DEFAULT_SH, _DEFAULT_BENCH, _DEFAULT_POS)


class Command(BaseCommand):
    help = (
        'Convert Phase 1A text inventory fields to structured FK models. '
        'Idempotent — safe to run multiple times.'
    )

    def handle(self, *args, **options):
        units = list(TrackingUnit.objects.all())

        created_crops = 0
        created_accessions = 0
        created_batches = 0
        created_positions = 0
        updated_units = 0
        skipped_units = 0

        for unit in units:
            changed = False

            # ── Crop ──────────────────────────────────────────────────────────
            if unit.crop_name and unit.crop_id is None:
                crop, created = Crop.objects.get_or_create(name=unit.crop_name)
                if created:
                    created_crops += 1
                    self.stdout.write(f'  CROP+    {crop.name}')
                unit.crop = crop
                changed = True

            # ── Accession ─────────────────────────────────────────────────────
            if unit.accession_code and unit.accession_id is None:
                # Accession.crop is required — only proceed if crop is available
                crop = unit.crop
                if crop is not None:
                    accession, created = Accession.objects.get_or_create(
                        accession_code=unit.accession_code,
                        defaults={'crop': crop},
                    )
                    if created:
                        created_accessions += 1
                        self.stdout.write(f'  ACC+     {accession.accession_code}')
                    unit.accession = accession
                    changed = True
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  SKIP ACC {unit.unit_code}: '
                            f'accession_code={unit.accession_code!r} but no crop — skipping'
                        )
                    )

            # ── Batch ─────────────────────────────────────────────────────────
            if unit.batch_code and unit.batch_id is None:
                accession = unit.accession
                if accession is not None:
                    batch, created = Batch.objects.get_or_create(
                        batch_code=unit.batch_code,
                        defaults={'accession': accession},
                    )
                    if created:
                        created_batches += 1
                        self.stdout.write(f'  BATCH+   {batch.batch_code}')
                    unit.batch = batch
                    changed = True
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  SKIP BCH {unit.unit_code}: '
                            f'batch_code={unit.batch_code!r} but no accession — skipping'
                        )
                    )

            # ── Position ──────────────────────────────────────────────────────
            if unit.location_text and unit.position_id is None:
                sh_name, bench_name, pos_code = _parse_location(unit.location_text)
                site, _ = Site.objects.get_or_create(name=_DEFAULT_SITE)
                sh, _ = ScreenHouse.objects.get_or_create(site=site, name=sh_name)
                bench, _ = Bench.objects.get_or_create(screen_house=sh, name=bench_name)
                position, created = Position.objects.get_or_create(bench=bench, code=pos_code)
                if created:
                    created_positions += 1
                    self.stdout.write(f'  POS+     {position}')
                unit.position = position
                changed = True

            if changed:
                unit.save(update_fields=['crop', 'accession', 'batch', 'position'])
                updated_units += 1
            else:
                skipped_units += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done.'))
        self.stdout.write(f'  Crops created:      {created_crops}')
        self.stdout.write(f'  Accessions created: {created_accessions}')
        self.stdout.write(f'  Batches created:    {created_batches}')
        self.stdout.write(f'  Positions created:  {created_positions}')
        self.stdout.write(f'  Units updated:      {updated_units}')
        self.stdout.write(f'  Units skipped:      {skipped_units}')
