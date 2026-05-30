from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from inventory.models import TrackingUnit


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
        # 0 is valid (e.g. all plants in a container died)
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
