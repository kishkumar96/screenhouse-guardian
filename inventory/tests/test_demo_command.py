from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from inventory.models import (
    Accession, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)


class CreateDemoTrackingUnitsCommandTest(TestCase):

    def _call(self):
        out = StringIO()
        call_command('create_demo_tracking_units', stdout=out)
        return out.getvalue()

    def test_command_creates_expected_units(self):
        self._call()
        codes = list(TrackingUnit.objects.values_list('unit_code', flat=True))
        self.assertIn('TU-CAS-0001', codes)
        self.assertIn('TU-TAR-0001', codes)
        self.assertIn('TU-BAN-0001', codes)
        self.assertIn('TU-KAV-0001', codes)

    def test_command_creates_correct_unit_count(self):
        self._call()
        self.assertEqual(TrackingUnit.objects.count(), 4)

    def test_command_sets_crop_names(self):
        self._call()
        self.assertTrue(TrackingUnit.objects.filter(unit_code='TU-CAS-0001', crop_name='Cassava').exists())
        self.assertTrue(TrackingUnit.objects.filter(unit_code='TU-TAR-0001', crop_name='Taro').exists())
        self.assertTrue(TrackingUnit.objects.filter(unit_code='TU-BAN-0001', crop_name='Banana').exists())
        self.assertTrue(TrackingUnit.objects.filter(unit_code='TU-KAV-0001', crop_name='Kava').exists())

    def test_command_sets_quantities(self):
        self._call()
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-CAS-0001').quantity, 20)
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-TAR-0001').quantity, 10)
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-BAN-0001').quantity, 1)
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-KAV-0001').quantity, 5)

    def test_command_sets_location_text(self):
        self._call()
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-CAS-0001').location_text, 'SH1 / Bench A')
        self.assertEqual(TrackingUnit.objects.get(unit_code='TU-TAR-0001').location_text, 'SH1 / Bench B')

    def test_command_is_idempotent(self):
        self._call()
        self._call()
        self.assertEqual(TrackingUnit.objects.count(), 4)

    def test_command_does_not_duplicate_existing_unit_code(self):
        TrackingUnit.objects.create(
            unit_code='TU-CAS-0001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Pre-existing Cassava',
            quantity=99,
        )
        self._call()
        self.assertEqual(
            TrackingUnit.objects.filter(unit_code='TU-CAS-0001').count(), 1
        )
        self.assertEqual(
            TrackingUnit.objects.get(unit_code='TU-CAS-0001').quantity, 99,
            'Existing record must not be overwritten',
        )

    def test_command_prints_created_output(self):
        output = self._call()
        self.assertIn('CREATE', output)
        self.assertIn('TU-CAS-0001', output)

    def test_command_prints_skipped_output_on_second_run(self):
        self._call()
        output = self._call()
        self.assertIn('SKIP', output)

    def test_command_prints_summary_counts(self):
        output = self._call()
        self.assertIn('Created:', output)
        self.assertIn('Skipped:', output)

    def test_banana_is_individual_unit_type(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-BAN-0001')
        self.assertEqual(unit.unit_type, TrackingUnit.UNIT_TYPE_INDIVIDUAL)

    def test_cassava_is_container_unit_type(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-CAS-0001')
        self.assertEqual(unit.unit_type, TrackingUnit.UNIT_TYPE_CONTAINER)

    def test_command_does_not_create_observations(self):
        from monitoring.models import Observation
        self._call()
        self.assertEqual(Observation.objects.count(), 0)

    # ── Phase 1B structured record tests ─────────────────────────────────────

    def test_command_creates_structured_crop_records(self):
        self._call()
        self.assertTrue(Crop.objects.filter(name='Cassava').exists())
        self.assertTrue(Crop.objects.filter(name='Taro').exists())
        self.assertTrue(Crop.objects.filter(name='Banana').exists())
        self.assertTrue(Crop.objects.filter(name='Kava').exists())

    def test_command_creates_structured_accession_records(self):
        self._call()
        self.assertTrue(Accession.objects.filter(accession_code='CAS-ACC-001').exists())
        self.assertTrue(Accession.objects.filter(accession_code='TAR-ACC-001').exists())
        self.assertTrue(Accession.objects.filter(accession_code='BAN-ACC-001').exists())
        self.assertTrue(Accession.objects.filter(accession_code='KAV-ACC-001').exists())

    def test_command_creates_structured_location_records(self):
        self._call()
        self.assertTrue(Site.objects.filter(name='Default Site').exists())
        self.assertTrue(ScreenHouse.objects.filter(name='SH1').exists())
        for bench_name in ['Bench A', 'Bench B', 'Bench C', 'Bench D']:
            self.assertTrue(Bench.objects.filter(name=bench_name).exists())
        self.assertTrue(Position.objects.filter(code='Unspecified').exists())

    def test_demo_units_have_crop_fk_set(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-CAS-0001')
        self.assertIsNotNone(unit.crop_id)
        self.assertEqual(unit.crop.name, 'Cassava')

    def test_demo_units_have_accession_fk_set(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-CAS-0001')
        self.assertIsNotNone(unit.accession_id)
        self.assertEqual(unit.accession.accession_code, 'CAS-ACC-001')

    def test_demo_units_have_position_fk_set(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-CAS-0001')
        self.assertIsNotNone(unit.position_id)

    def test_structured_records_idempotent_on_second_run(self):
        self._call()
        self._call()
        self.assertEqual(Crop.objects.filter(name='Cassava').count(), 1)
        self.assertEqual(Accession.objects.filter(accession_code='CAS-ACC-001').count(), 1)

    def test_legacy_text_fields_still_populated(self):
        self._call()
        unit = TrackingUnit.objects.get(unit_code='TU-CAS-0001')
        self.assertEqual(unit.crop_name, 'Cassava')
        self.assertEqual(unit.accession_code, 'CAS-ACC-001')
        self.assertEqual(unit.location_text, 'SH1 / Bench A')
