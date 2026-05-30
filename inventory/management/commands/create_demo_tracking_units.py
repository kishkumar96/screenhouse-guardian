from django.core.management.base import BaseCommand

from inventory.models import (
    Accession, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)

_DEMO_SITE = 'Default Site'
_DEMO_SH = 'SH1'

DEMO_UNITS = [
    {
        'unit_code': 'TU-CAS-0001',
        'crop_name': 'Cassava',
        'accession_code': 'CAS-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_POT,
        'quantity': 20,
        'location_text': 'SH1 / Bench A',
        '_bench': 'Bench A',
    },
    {
        'unit_code': 'TU-TAR-0001',
        'crop_name': 'Taro',
        'accession_code': 'TAR-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_TRAY,
        'quantity': 10,
        'location_text': 'SH1 / Bench B',
        '_bench': 'Bench B',
    },
    {
        'unit_code': 'TU-BAN-0001',
        'crop_name': 'Banana',
        'accession_code': 'BAN-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_INDIVIDUAL,
        'container_type': '',
        'quantity': 1,
        'location_text': 'SH1 / Bench C',
        '_bench': 'Bench C',
    },
    {
        'unit_code': 'TU-KAV-0001',
        'crop_name': 'Kava',
        'accession_code': 'KAV-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_NURSERY_BAG,
        'quantity': 5,
        'location_text': 'SH1 / Bench D',
        '_bench': 'Bench D',
    },
]


def _build_structured_records():
    """
    Ensure Crop, Accession, Site, ScreenHouse, Bench, and Position records
    exist for all demo units.  Returns a lookup dict keyed by unit_code.
    """
    site, _ = Site.objects.get_or_create(name=_DEMO_SITE)
    sh, _ = ScreenHouse.objects.get_or_create(site=site, name=_DEMO_SH)

    structured = {}
    for spec in DEMO_UNITS:
        crop, _ = Crop.objects.get_or_create(name=spec['crop_name'])
        accession, _ = Accession.objects.get_or_create(
            accession_code=spec['accession_code'],
            defaults={'crop': crop},
        )
        bench, _ = Bench.objects.get_or_create(screen_house=sh, name=spec['_bench'])
        position, _ = Position.objects.get_or_create(bench=bench, code='Unspecified')
        structured[spec['unit_code']] = {
            'crop': crop,
            'accession': accession,
            'position': position,
        }
    return structured


class Command(BaseCommand):
    help = 'Create a small set of demo TrackingUnit records for pilot testing.'

    def handle(self, *args, **options):
        structured = _build_structured_records()

        created = 0
        skipped = 0

        for spec in DEMO_UNITS:
            unit_code = spec['unit_code']
            if TrackingUnit.objects.filter(unit_code=unit_code).exists():
                self.stdout.write(f'  SKIP   {unit_code} — already exists')
                skipped += 1
            else:
                fk = structured[unit_code]
                unit_fields = {
                    k: v for k, v in spec.items() if not k.startswith('_')
                }
                TrackingUnit.objects.create(
                    **unit_fields,
                    crop=fk['crop'],
                    accession=fk['accession'],
                    position=fk['position'],
                )
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
