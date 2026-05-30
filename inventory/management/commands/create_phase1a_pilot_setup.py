from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from inventory.models import TrackingUnit


PILOT_UNITS = [
    {
        'unit_code': 'TU-CAS-0001',
        'crop_name': 'Cassava',
        'accession_code': 'CAS-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_POT,
        'quantity': 24,
        'location_text': 'SH1 / Bench A1',
    },
    {
        'unit_code': 'TU-CAS-0002',
        'crop_name': 'Cassava',
        'accession_code': 'CAS-ACC-002',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_POT,
        'quantity': 18,
        'location_text': 'SH1 / Bench A2',
    },
    {
        'unit_code': 'TU-TAR-0001',
        'crop_name': 'Taro',
        'accession_code': 'TAR-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_TRAY,
        'quantity': 12,
        'location_text': 'SH1 / Bench B1',
    },
    {
        'unit_code': 'TU-TAR-0002',
        'crop_name': 'Taro',
        'accession_code': 'TAR-ACC-002',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_TRAY,
        'quantity': 10,
        'location_text': 'SH1 / Bench B2',
    },
    {
        'unit_code': 'TU-BAN-0001',
        'crop_name': 'Banana',
        'accession_code': 'BAN-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_INDIVIDUAL,
        'container_type': '',
        'quantity': 1,
        'location_text': 'SH1 / Bench C1',
    },
    {
        'unit_code': 'TU-BAN-0002',
        'crop_name': 'Banana',
        'accession_code': 'BAN-ACC-002',
        'unit_type': TrackingUnit.UNIT_TYPE_INDIVIDUAL,
        'container_type': '',
        'quantity': 1,
        'location_text': 'SH1 / Bench C2',
    },
    {
        'unit_code': 'TU-KAV-0001',
        'crop_name': 'Kava',
        'accession_code': 'KAV-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_NURSERY_BAG,
        'quantity': 6,
        'location_text': 'SH1 / Bench D1',
    },
    {
        'unit_code': 'TU-KAV-0002',
        'crop_name': 'Kava',
        'accession_code': 'KAV-ACC-002',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_NURSERY_BAG,
        'quantity': 5,
        'location_text': 'SH1 / Bench D2',
    },
    {
        'unit_code': 'TU-COC-0001',
        'crop_name': 'Coconut',
        'accession_code': 'COC-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_OTHER,
        'quantity': 8,
        'location_text': 'SH1 / Bench E1',
    },
    {
        'unit_code': 'TU-PAP-0001',
        'crop_name': 'Papaya',
        'accession_code': 'PAP-ACC-001',
        'unit_type': TrackingUnit.UNIT_TYPE_CONTAINER,
        'container_type': TrackingUnit.CONTAINER_TYPE_SEEDLING_TRAY,
        'quantity': 16,
        'location_text': 'SH1 / Bench F1',
    },
]


class Command(BaseCommand):
    help = 'Create a 10-unit Phase 1A pilot dataset plus Manager and Observer users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--manager-username',
            default='pilot_manager',
            help='Username for the Manager pilot user.',
        )
        parser.add_argument(
            '--observer-username',
            default='pilot_observer',
            help='Username for the Observer pilot user.',
        )
        parser.add_argument(
            '--password',
            default='pilotpass123',
            help='Password to set for created pilot users.',
        )

    def handle(self, *args, **options):
        manager_username = options['manager_username']
        observer_username = options['observer_username']
        password = options['password']

        manager_group, _ = Group.objects.get_or_create(name='Manager')
        observer_group, _ = Group.objects.get_or_create(name='Observer')

        User = get_user_model()
        created_users = 0
        skipped_users = 0

        manager_user, manager_created = User.objects.get_or_create(
            username=manager_username,
            defaults={'is_active': True},
        )
        if manager_created:
            manager_user.set_password(password)
            manager_user.save()
            created_users += 1
            self.stdout.write(self.style.SUCCESS(f'  CREATE USER {manager_username} (Manager)'))
        else:
            skipped_users += 1
            self.stdout.write(f'  SKIP USER   {manager_username} — already exists')
        manager_user.groups.add(manager_group)

        observer_user, observer_created = User.objects.get_or_create(
            username=observer_username,
            defaults={'is_active': True},
        )
        if observer_created:
            observer_user.set_password(password)
            observer_user.save()
            created_users += 1
            self.stdout.write(self.style.SUCCESS(f'  CREATE USER {observer_username} (Observer)'))
        else:
            skipped_users += 1
            self.stdout.write(f'  SKIP USER   {observer_username} — already exists')
        observer_user.groups.add(observer_group)

        created_units = 0
        skipped_units = 0
        for spec in PILOT_UNITS:
            unit_code = spec['unit_code']
            if TrackingUnit.objects.filter(unit_code=unit_code).exists():
                self.stdout.write(f'  SKIP UNIT   {unit_code} — already exists')
                skipped_units += 1
            else:
                TrackingUnit.objects.create(**spec)
                created_units += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  CREATE UNIT {unit_code} — {spec["crop_name"]} '
                        f'qty={spec["quantity"]} loc={spec["location_text"]}'
                    )
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Phase 1A pilot setup complete.'))
        self.stdout.write(f'Users created: {created_users}  skipped: {skipped_users}')
        self.stdout.write(f'Units created: {created_units}  skipped: {skipped_units}')
        self.stdout.write(f'Manager login:  {manager_username}')
        self.stdout.write(f'Observer login: {observer_username}')
