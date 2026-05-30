from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import TrackingUnit
from monitoring.models import QuantityEvent
from monitoring.services import apply_quantity_event


def make_container(unit_code='TU-SVC-001', quantity=10):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=quantity,
    )


class ApplyQuantityEventServiceTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='service-user',
            password='test-password-123',
        )

    def test_death_event_decreases_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-DEATH-001', quantity=50)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-4,
            user=self.user,
            reason='Routine culling.',
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 46)
        self.assertEqual(event.quantity_before, 50)
        self.assertEqual(event.quantity_change, -4)
        self.assertEqual(event.quantity_after, 46)

    def test_loss_event_decreases_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-LOSS-001', quantity=12)

        apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_LOSS,
            quantity_change=-2,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 10)

    def test_correction_event_can_increase_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-CORR-001', quantity=8)

        apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=3,
            user=self.user,
            reason='Recount found additional seedlings.',
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 11)

    def test_negative_result_raises_validation_error(self):
        unit = make_container('TU-SVC-NEG-001', quantity=3)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_DEATH,
                quantity_change=-5,
                user=self.user,
            )

        self.assertIn('quantity_change', ctx.exception.message_dict)

    def test_negative_result_creates_no_event_and_leaves_quantity_unchanged(self):
        unit = make_container('TU-SVC-NEG-002', quantity=3)

        with self.assertRaises(ValidationError):
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_LOSS,
                quantity_change=-10,
                user=self.user,
            )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 3)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=unit).count(), 0)

    def test_created_event_has_expected_fields(self):
        unit = make_container('TU-SVC-FIELDS-001', quantity=20)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_LOSS,
            quantity_change=-6,
            user=self.user,
            reason='Storm damage.',
        )

        self.assertEqual(event.quantity_before, 20)
        self.assertEqual(event.quantity_change, -6)
        self.assertEqual(event.quantity_after, 14)
        self.assertEqual(event.event_type, QuantityEvent.EVENT_TYPE_LOSS)
        self.assertEqual(event.reason, 'Storm damage.')
        self.assertEqual(event.created_by, self.user)

    def test_service_returns_created_quantity_event(self):
        unit = make_container('TU-SVC-RETURN-001', quantity=7)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=1,
            user=self.user,
        )

        self.assertIsInstance(event, QuantityEvent)
        self.assertIsNotNone(event.pk)

    def test_service_works_with_tracking_unit_id(self):
        unit = make_container('TU-SVC-ID-001', quantity=15)

        event = apply_quantity_event(
            tracking_unit_id=unit.pk,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-5,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 10)
        self.assertEqual(event.tracking_unit_id, unit.pk)

    def test_service_works_with_tracking_unit_instance(self):
        unit = make_container('TU-SVC-INSTANCE-001', quantity=9)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=2,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 11)
        self.assertEqual(event.tracking_unit, unit)

    def test_invalid_event_type_raises_validation_error(self):
        unit = make_container('TU-SVC-TYPE-001', quantity=9)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type='bad_type',
                quantity_change=-1,
                user=self.user,
            )

        self.assertIn('event_type', ctx.exception.message_dict)

    def test_non_integer_quantity_change_raises_validation_error(self):
        unit = make_container('TU-SVC-INT-001', quantity=9)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_DEATH,
                quantity_change='-1',
                user=self.user,
            )

        self.assertIn('quantity_change', ctx.exception.message_dict)

    def test_service_allows_user_none(self):
        unit = make_container('TU-SVC-USER-001', quantity=5)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=1,
            user=None,
        )

        self.assertIsNone(event.created_by)
