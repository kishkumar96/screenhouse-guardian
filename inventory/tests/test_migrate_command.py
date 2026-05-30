from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from inventory.models import (
    Accession, Batch, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)


def _call(**kwargs):
    out = StringIO()
    call_command('migrate_phase1a_inventory', stdout=out, **kwargs)
    return out.getvalue()


def _make_unit(unit_code, **overrides):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Cassava',
        accession_code='CAS-ACC-001',
        batch_code='',
        location_text='SH1 / Bench A',
    )
    defaults.update(overrides)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


class MigratePhase1aInventoryCropTest(TestCase):

    def test_creates_crop_from_crop_name(self):
        _make_unit('TU-M-001', crop_name='Taro')
        _call()
        self.assertTrue(Crop.objects.filter(name='Taro').exists())

    def test_links_tracking_unit_to_crop(self):
        unit = _make_unit('TU-M-002', crop_name='Banana')
        _call()
        unit.refresh_from_db()
        self.assertIsNotNone(unit.crop_id)
        self.assertEqual(unit.crop.name, 'Banana')

    def test_does_not_create_duplicate_crop(self):
        _make_unit('TU-M-003', crop_name='Kava')
        _make_unit('TU-M-004', crop_name='Kava')
        _call()
        self.assertEqual(Crop.objects.filter(name='Kava').count(), 1)

    def test_skips_crop_when_crop_name_is_blank(self):
        # crop_name cannot actually be blank on creation (field has no blank=True)
        # but if it were, we must not crash
        unit = TrackingUnit.objects.create(
            unit_code='TU-M-BLANK',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='PlaceholderForBlankTest',
        )
        # Manually force crop_name to empty to simulate edge case
        TrackingUnit.objects.filter(pk=unit.pk).update(crop_name='')
        unit.refresh_from_db()
        _call()
        unit.refresh_from_db()
        self.assertIsNone(unit.crop_id)


class MigratePhase1aInventoryAccessionTest(TestCase):

    def test_creates_accession_from_accession_code(self):
        _make_unit('TU-A-001', crop_name='Cassava', accession_code='CAS-ACC-001')
        _call()
        self.assertTrue(Accession.objects.filter(accession_code='CAS-ACC-001').exists())

    def test_links_tracking_unit_to_accession(self):
        unit = _make_unit('TU-A-002', crop_name='Cassava', accession_code='CAS-ACC-002')
        _call()
        unit.refresh_from_db()
        self.assertIsNotNone(unit.accession_id)
        self.assertEqual(unit.accession.accession_code, 'CAS-ACC-002')

    def test_accession_linked_to_crop(self):
        _make_unit('TU-A-003', crop_name='Taro', accession_code='TAR-ACC-001')
        _call()
        acc = Accession.objects.get(accession_code='TAR-ACC-001')
        self.assertEqual(acc.crop.name, 'Taro')

    def test_skips_accession_when_no_crop_available(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-A-NOCROP',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='PlaceholderForBlankTest',
            accession_code='NO-CROP-ACC',
        )
        TrackingUnit.objects.filter(pk=unit.pk).update(crop_name='')
        unit.refresh_from_db()
        _call()
        unit.refresh_from_db()
        self.assertIsNone(unit.accession_id)


class MigratePhase1aInventoryBatchTest(TestCase):

    def test_creates_batch_from_batch_code(self):
        _make_unit('TU-B-001', crop_name='Cassava', accession_code='CAS-ACC-BCH', batch_code='CAS-BCH-001')
        _call()
        self.assertTrue(Batch.objects.filter(batch_code='CAS-BCH-001').exists())

    def test_links_tracking_unit_to_batch(self):
        unit = _make_unit('TU-B-002', crop_name='Cassava', accession_code='CAS-ACC-BCH2', batch_code='CAS-BCH-002')
        _call()
        unit.refresh_from_db()
        self.assertIsNotNone(unit.batch_id)
        self.assertEqual(unit.batch.batch_code, 'CAS-BCH-002')

    def test_skips_batch_when_accession_code_empty(self):
        unit = _make_unit('TU-B-NOACC', crop_name='Cassava', accession_code='', batch_code='ORPHAN-BCH')
        _call()
        unit.refresh_from_db()
        self.assertIsNone(unit.batch_id)


class MigratePhase1aInventoryLocationTest(TestCase):

    def test_creates_position_from_location_text_two_parts(self):
        _make_unit('TU-L-001', location_text='SH1 / Bench A')
        _call()
        self.assertTrue(Site.objects.filter(name='Default Site').exists())
        self.assertTrue(ScreenHouse.objects.filter(name='SH1').exists())
        self.assertTrue(Bench.objects.filter(name='Bench A').exists())
        self.assertTrue(Position.objects.filter(code='Unspecified').exists())

    def test_creates_position_from_location_text_three_parts(self):
        _make_unit('TU-L-002', location_text='SH2 / Bench B / Position 3')
        _call()
        self.assertTrue(ScreenHouse.objects.filter(name='SH2').exists())
        self.assertTrue(Bench.objects.filter(name='Bench B').exists())
        self.assertTrue(Position.objects.filter(code='Position 3').exists())

    def test_links_tracking_unit_to_position(self):
        unit = _make_unit('TU-L-003', location_text='SH1 / Bench C')
        _call()
        unit.refresh_from_db()
        self.assertIsNotNone(unit.position_id)

    def test_creates_fallback_location_for_single_part_location_text(self):
        unit = _make_unit('TU-L-004', location_text='Bay 7')
        _call()
        unit.refresh_from_db()
        self.assertIsNotNone(unit.position_id)
        self.assertEqual(unit.position.bench.name, 'Bay 7')

    def test_skips_location_when_location_text_is_empty(self):
        unit = _make_unit('TU-L-005', location_text='')
        _call()
        unit.refresh_from_db()
        self.assertIsNone(unit.position_id)


class MigratePhase1aInventoryIdempotencyTest(TestCase):

    def test_command_is_idempotent(self):
        _make_unit('TU-IDEM-001', crop_name='Cassava', accession_code='CAS-ACC-IDEM')
        _call()
        _call()
        self.assertEqual(Crop.objects.filter(name='Cassava').count(), 1)
        self.assertEqual(Accession.objects.filter(accession_code='CAS-ACC-IDEM').count(), 1)

    def test_second_run_does_not_change_fk_values(self):
        unit = _make_unit('TU-IDEM-002', crop_name='Banana', accession_code='BAN-ACC-IDEM')
        _call()
        unit.refresh_from_db()
        crop_id_after_first = unit.crop_id
        accession_id_after_first = unit.accession_id
        _call()
        unit.refresh_from_db()
        self.assertEqual(unit.crop_id, crop_id_after_first)
        self.assertEqual(unit.accession_id, accession_id_after_first)

    def test_legacy_text_fields_not_removed(self):
        unit = _make_unit('TU-IDEM-003', crop_name='Kava', accession_code='KAV-ACC-IDEM')
        _call()
        unit.refresh_from_db()
        self.assertEqual(unit.crop_name, 'Kava')
        self.assertEqual(unit.accession_code, 'KAV-ACC-IDEM')

    def test_units_already_linked_are_skipped(self):
        crop = Crop.objects.create(name='Pre-linked Crop')
        unit = _make_unit('TU-IDEM-004', crop_name='Pre-linked Crop', accession_code='')
        unit.crop = crop
        unit.save(update_fields=['crop'])
        _call()
        unit.refresh_from_db()
        self.assertEqual(unit.crop_id, crop.pk)

    def test_command_outputs_summary(self):
        _make_unit('TU-IDEM-005', crop_name='Summary Crop', accession_code='')
        output = _call()
        self.assertIn('Done.', output)
        self.assertIn('Units updated:', output)
        self.assertIn('Units skipped:', output)
