from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import TrackingUnit
from monitoring.models import Observation, QuantityEvent


def make_container(unit_code='TU-ADMIN-001', quantity=10):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=quantity,
    )


class ImmutableAdminTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-password-123',
        )
        self.client.force_login(self.user)

    def test_observation_change_view_is_read_only(self):
        unit = make_container('TU-ADMIN-OBS-001')
        observation = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
            notes='Original note',
        )

        response = self.client.get(
            reverse('admin:monitoring_observation_change', args=[observation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View observation')

    def test_observation_change_post_is_forbidden(self):
        unit = make_container('TU-ADMIN-OBS-002')
        observation = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
        )

        response = self.client.post(
            reverse('admin:monitoring_observation_change', args=[observation.pk]),
            data={
                'tracking_unit': unit.pk,
                'observation_type': observation.observation_type,
                'status': Observation.STATUS_SICK,
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_quantity_event_change_view_is_read_only(self):
        unit = make_container('TU-ADMIN-QE-001')
        event = QuantityEvent.objects.create(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=10,
            quantity_change=-1,
            quantity_after=9,
        )

        response = self.client.get(
            reverse('admin:monitoring_quantityevent_change', args=[event.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'View quantity event')

    def test_quantity_event_change_post_is_forbidden(self):
        unit = make_container('TU-ADMIN-QE-002')
        event = QuantityEvent.objects.create(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=10,
            quantity_change=-1,
            quantity_after=9,
        )

        response = self.client.post(
            reverse('admin:monitoring_quantityevent_change', args=[event.pk]),
            data={
                'tracking_unit': unit.pk,
                'event_type': event.event_type,
                'quantity_before': event.quantity_before,
                'quantity_change': event.quantity_change,
                'quantity_after': event.quantity_after,
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 403)
