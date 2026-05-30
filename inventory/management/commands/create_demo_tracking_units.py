from django.core.management.base import BaseCommand

from inventory.models import TrackingUnit

DEMO_UNITS = [
    {
        'unit_code': 'TU-CAS-0001',
        'crop_name': 'Cassava',
        'accession_code': 'CAS-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_POT,
        'quantity': 20,
        'location_text': 'SH1 / Bench A',
    },
    {
        'unit_code': 'TU-TAR-0001',
        'crop_name': 'Taro',
        'accession_code': 'TAR-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_TRAY,
        'quantity': 10,
        'location_text': 'SH1 / Bench B',
    },
    {
        'unit_code': 'TU-BAN-0001',
        'crop_name': 'Banana',
        'accession_code': 'BAN-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_INDIVIDUAL,
        'container_type': '',
        'quantity': 1,
        'location_text': 'SH1 / Bench C',
    },
    {
        'unit_code': 'TU-KAV-0001',
        'crop_name': 'Kava',
        'accession_code': 'KAV-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_NURSERY_BAG,
        'quantity': 5,
        'location_text': 'SH1 / Bench D',
    },
]


class Command(BaseCommand):
    help = 'Create a small set of demo TrackingUnit records for pilot testing.'

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for spec in DEMO_UNITS:
            unit_code = spec['unit_code']
            if TrackingUnit.objects.filter(unit_code=unit_code).exists():
                self.stdout.write(f'  SKIP   {unit_code} — already exists')
                skipped += 1
            else:
                TrackingUnit.objects.create(**spec)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  CREATE {unit_code} — {spec["crop_name"]} '
                        f'qty={spec["quantity"]} loc={spec["location_text"]}'
                    )
                )
                created += 1

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Done. Created: {created}  Skipped: {skipped}')
        )
