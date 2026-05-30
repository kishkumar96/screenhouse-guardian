from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from inventory.models import (
    Accession, Batch, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)


def make_unit(**overrides):
    """Return an unsaved TrackingUnit with sensible defaults."""
    defaults = dict(
        unit_code='TU-TEST-001',
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
    )
    defaults.update(overrides)
    return TrackingUnit(**defaults)


# ── Phase 1A TrackingUnit tests (unchanged) ───────────────────────────────────

class TrackingUnitCreationTest(TestCase):

    def test_can_create_container_unit(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-C-001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Baobab',
            container_type=TrackingUnit.CONTAINER_TYPE_TRAY,
            quantity=50,
        )
        self.assertEqual(unit.unit_code, 'TU-C-001')
        self.assertEqual(unit.unit_type, TrackingUnit.UNIT_TYPE_CONTAINER)
        self.assertTrue(unit.is_active)

    def test_can_create_individual_unit(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-I-001',
            unit_type=TrackingUnit.UNIT_TYPE_INDIVIDUAL,
            crop_name='Cycad',
            quantity=1,
        )
        self.assertEqual(unit.unit_type, TrackingUnit.UNIT_TYPE_INDIVIDUAL)
        self.assertEqual(unit.quantity, 1)

    def test_str_representation(self):
        unit = make_unit(unit_code='TU-STR-001')
        self.assertIn('TU-STR-001', str(unit))


class TrackingUnitUniqueCodeTest(TestCase):

    def test_unit_code_must_be_unique(self):
        TrackingUnit.objects.create(
            unit_code='TU-DUP-001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Cycad',
        )
        with self.assertRaises(IntegrityError):
            TrackingUnit.objects.create(
                unit_code='TU-DUP-001',
                unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
                crop_name='Baobab',
            )

    def test_unit_code_uniqueness_via_full_clean(self):
        TrackingUnit.objects.create(
            unit_code='TU-DUP-002',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Cycad',
        )
        duplicate = make_unit(unit_code='TU-DUP-002')
        with self.assertRaises(ValidationError) as ctx:
            duplicate.full_clean()
        self.assertIn('unit_code', ctx.exception.message_dict)


class TrackingUnitQuantityTest(TestCase):

    def test_quantity_cannot_be_negative(self):
        unit = make_unit(quantity=-1)
        with self.assertRaises(ValidationError):
            unit.full_clean()

    def test_quantity_zero_is_allowed(self):
        unit = make_unit(unit_code='TU-Q-001', quantity=0)
        unit.full_clean()

    def test_positive_quantity_is_valid(self):
        unit = make_unit(unit_code='TU-Q-002', quantity=100)
        unit.full_clean()


class TrackingUnitIndividualQuantityTest(TestCase):

    def test_individual_unit_with_quantity_greater_than_1_raises_error(self):
        unit = make_unit(
            unit_code='TU-IND-001',
            unit_type=TrackingUnit.UNIT_TYPE_INDIVIDUAL,
            quantity=5,
        )
        with self.assertRaises(ValidationError) as ctx:
            unit.full_clean()
        self.assertIn('quantity', ctx.exception.message_dict)

    def test_individual_unit_with_quantity_1_is_valid(self):
        unit = make_unit(
            unit_code='TU-IND-002',
            unit_type=TrackingUnit.UNIT_TYPE_INDIVIDUAL,
            quantity=1,
        )
        unit.full_clean()

    def test_container_unit_with_high_quantity_is_valid(self):
        unit = make_unit(
            unit_code='TU-IND-003',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            quantity=500,
        )
        unit.full_clean()


class TrackingUnitContainerTypeTest(TestCase):

    def test_individual_unit_with_container_type_raises_error(self):
        unit = make_unit(
            unit_code='TU-CT-001',
            unit_type=TrackingUnit.UNIT_TYPE_INDIVIDUAL,
            quantity=1,
            container_type=TrackingUnit.CONTAINER_TYPE_TRAY,
        )
        with self.assertRaises(ValidationError) as ctx:
            unit.full_clean()
        self.assertIn('container_type', ctx.exception.message_dict)

    def test_container_unit_with_container_type_is_valid(self):
        unit = make_unit(
            unit_code='TU-CT-002',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            container_type=TrackingUnit.CONTAINER_TYPE_TRAY,
        )
        unit.full_clean()


# ── Phase 1B: Crop ────────────────────────────────────────────────────────────

class CropModelTest(TestCase):

    def test_can_create_crop(self):
        crop = Crop.objects.create(name='Cassava')
        self.assertEqual(crop.name, 'Cassava')
        self.assertTrue(crop.is_active)

    def test_crop_name_is_unique(self):
        Crop.objects.create(name='Taro')
        with self.assertRaises(IntegrityError):
            Crop.objects.create(name='Taro')

    def test_crop_str(self):
        crop = Crop.objects.create(name='Banana')
        self.assertEqual(str(crop), 'Banana')

    def test_optional_fields_are_blank(self):
        crop = Crop.objects.create(name='Kava')
        self.assertEqual(crop.scientific_name, '')
        self.assertEqual(crop.category, '')
        self.assertEqual(crop.notes, '')


# ── Phase 1B: Accession ───────────────────────────────────────────────────────

class AccessionModelTest(TestCase):

    def setUp(self):
        self.crop = Crop.objects.create(name='Cassava')

    def test_accession_belongs_to_crop(self):
        acc = Accession.objects.create(
            crop=self.crop, accession_code='CAS-ACC-001'
        )
        self.assertEqual(acc.crop, self.crop)

    def test_accession_code_is_unique(self):
        Accession.objects.create(crop=self.crop, accession_code='CAS-ACC-DUP')
        with self.assertRaises(IntegrityError):
            Accession.objects.create(crop=self.crop, accession_code='CAS-ACC-DUP')

    def test_accession_str(self):
        acc = Accession.objects.create(crop=self.crop, accession_code='CAS-ACC-STR')
        self.assertEqual(str(acc), 'CAS-ACC-STR')


# ── Phase 1B: Batch ───────────────────────────────────────────────────────────

class BatchModelTest(TestCase):

    def setUp(self):
        crop = Crop.objects.create(name='Taro')
        self.accession = Accession.objects.create(crop=crop, accession_code='TAR-ACC-001')

    def test_batch_belongs_to_accession(self):
        batch = Batch.objects.create(
            accession=self.accession, batch_code='TAR-BCH-001'
        )
        self.assertEqual(batch.accession, self.accession)

    def test_batch_code_is_unique(self):
        Batch.objects.create(accession=self.accession, batch_code='TAR-BCH-DUP')
        with self.assertRaises(IntegrityError):
            Batch.objects.create(accession=self.accession, batch_code='TAR-BCH-DUP')

    def test_batch_str(self):
        batch = Batch.objects.create(accession=self.accession, batch_code='TAR-BCH-STR')
        self.assertEqual(str(batch), 'TAR-BCH-STR')


# ── Phase 1B: Location hierarchy ─────────────────────────────────────────────

class LocationModelTest(TestCase):

    def setUp(self):
        self.site = Site.objects.create(name='Main Site')
        self.sh = ScreenHouse.objects.create(site=self.site, name='SH1')
        self.bench = Bench.objects.create(screen_house=self.sh, name='Bench A')

    def test_site_screen_house_bench_position_can_be_created(self):
        pos = Position.objects.create(bench=self.bench, code='P1')
        self.assertEqual(pos.bench, self.bench)
        self.assertEqual(pos.bench.screen_house, self.sh)
        self.assertEqual(pos.bench.screen_house.site, self.site)

    def test_screen_house_unique_by_site_and_name(self):
        with self.assertRaises(IntegrityError):
            ScreenHouse.objects.create(site=self.site, name='SH1')

    def test_bench_unique_by_screen_house_and_name(self):
        with self.assertRaises(IntegrityError):
            Bench.objects.create(screen_house=self.sh, name='Bench A')

    def test_position_unique_by_bench_and_code(self):
        Position.objects.create(bench=self.bench, code='P1')
        with self.assertRaises(IntegrityError):
            Position.objects.create(bench=self.bench, code='P1')

    def test_screen_house_str(self):
        self.assertEqual(str(self.sh), 'Main Site / SH1')

    def test_bench_str(self):
        self.assertIn('Bench A', str(self.bench))

    def test_position_str(self):
        pos = Position.objects.create(bench=self.bench, code='P99')
        self.assertIn('P99', str(pos))


# ── Phase 1B: TrackingUnit structured FK links ────────────────────────────────

class TrackingUnitStructuredLinksTest(TestCase):

    def setUp(self):
        self.crop = Crop.objects.create(name='Cassava')
        self.accession = Accession.objects.create(
            crop=self.crop, accession_code='CAS-ACC-001'
        )
        self.batch = Batch.objects.create(
            accession=self.accession, batch_code='CAS-BCH-001'
        )
        self.site = Site.objects.create(name='Test Site')
        self.sh = ScreenHouse.objects.create(site=self.site, name='SH1')
        self.bench = Bench.objects.create(screen_house=self.sh, name='Bench A')
        self.position = Position.objects.create(bench=self.bench, code='P1')

    def _make_linked_unit(self):
        return TrackingUnit.objects.create(
            unit_code='TU-LNK-001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Cassava',
            accession_code='CAS-ACC-001',
            batch_code='CAS-BCH-001',
            location_text='SH1 / Bench A',
            crop=self.crop,
            accession=self.accession,
            batch=self.batch,
            position=self.position,
        )

    def test_tracking_unit_can_link_to_crop_accession_batch_position(self):
        unit = self._make_linked_unit()
        unit.refresh_from_db()
        self.assertEqual(unit.crop, self.crop)
        self.assertEqual(unit.accession, self.accession)
        self.assertEqual(unit.batch, self.batch)
        self.assertEqual(unit.position, self.position)

    def test_display_crop_prefers_structured_fk(self):
        unit = self._make_linked_unit()
        self.assertEqual(unit.display_crop, 'Cassava')

    def test_display_accession_prefers_structured_fk(self):
        unit = self._make_linked_unit()
        self.assertEqual(unit.display_accession, 'CAS-ACC-001')

    def test_display_batch_prefers_structured_fk(self):
        unit = self._make_linked_unit()
        self.assertEqual(unit.display_batch, 'CAS-BCH-001')

    def test_display_location_prefers_structured_fk(self):
        unit = self._make_linked_unit()
        self.assertEqual(unit.display_location, 'Test Site / SH1 / Bench A / P1')

    def test_display_crop_falls_back_to_crop_name(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Legacy Crop',
        )
        self.assertEqual(unit.display_crop, 'Legacy Crop')

    def test_display_accession_falls_back_to_accession_code(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-002',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Legacy Crop',
            accession_code='LEGACY-ACC',
        )
        self.assertEqual(unit.display_accession, 'LEGACY-ACC')

    def test_display_batch_falls_back_to_batch_code(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-003',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Legacy Crop',
            batch_code='LEGACY-BCH',
        )
        self.assertEqual(unit.display_batch, 'LEGACY-BCH')

    def test_display_location_falls_back_to_location_text(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-004',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Legacy Crop',
            location_text='Old Bay 3',
        )
        self.assertEqual(unit.display_location, 'Old Bay 3')

    def test_display_accession_returns_empty_string_when_both_empty(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-005',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Crop',
        )
        self.assertEqual(unit.display_accession, '')

    def test_display_location_returns_empty_string_when_both_empty(self):
        unit = TrackingUnit.objects.create(
            unit_code='TU-FB-006',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Crop',
        )
        self.assertEqual(unit.display_location, '')
