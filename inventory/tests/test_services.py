from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import Bench, MovementHistory, Position, ScreenHouse, Site, TrackingUnit
from inventory.services import record_movement


def make_unit(unit_code='TU-SVC-MOVE-001', **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
        location_text='Bay A',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


def make_position(code='P1'):
    site = Site.objects.create(name=f'Site for {code}')
    sh = ScreenHouse.objects.create(site=site, name='SH1')
    bench = Bench.objects.create(screen_house=sh, name='Bench A')
    return Position.objects.create(bench=bench, code=code)


class RecordMovementServiceTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='move-service-user',
            password='test-password-123',
        )

    def test_move_to_structured_position_updates_unit(self):
        unit = make_unit('TU-SVC-MOVE-002')
        position = make_position('P2')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)

        unit.refresh_from_db()
        self.assertEqual(unit.position_id, position.pk)

    def test_move_to_structured_position_clears_nothing_unexpected(self):
        unit = make_unit('TU-SVC-MOVE-003', location_text='Old Bay')
        position = make_position('P3')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)

        unit.refresh_from_db()
        self.assertEqual(unit.position_id, position.pk)

    def test_move_to_free_text_location_clears_structured_position(self):
        position = make_position('P4')
        unit = make_unit('TU-SVC-MOVE-004', position=position)

        record_movement(tracking_unit=unit, to_location_text='New Bay', user=self.user)

        unit.refresh_from_db()
        self.assertIsNone(unit.position_id)
        self.assertEqual(unit.location_text, 'New Bay')

    def test_creates_movement_history_record_with_before_and_after(self):
        unit = make_unit('TU-SVC-MOVE-005', location_text='Bay A')
        position = make_position('P5')

        movement = record_movement(
            tracking_unit=unit, to_position=position, user=self.user, reason='Better light'
        )

        self.assertEqual(movement.from_location_text, 'Bay A')
        self.assertEqual(movement.to_position, position)
        self.assertEqual(movement.reason, 'Better light')
        self.assertEqual(MovementHistory.objects.filter(tracking_unit=unit).count(), 1)

    def test_requires_destination(self):
        unit = make_unit('TU-SVC-MOVE-006')

        with self.assertRaises(ValidationError):
            record_movement(tracking_unit=unit, user=self.user)

    def test_requires_tracking_unit(self):
        with self.assertRaises(ValidationError):
            record_movement(to_location_text='Bay Z', user=self.user)

    def test_second_move_captures_previous_destination_as_new_origin(self):
        unit = make_unit('TU-SVC-MOVE-007', location_text='Bay A')
        position = make_position('P7')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)
        second_movement = record_movement(
            tracking_unit=unit, to_location_text='Bay C', user=self.user
        )

        self.assertEqual(second_movement.from_position, position)
