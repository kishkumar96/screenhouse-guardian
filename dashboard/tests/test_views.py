from django.test import TestCase

from inventory.models import TrackingUnit
from monitoring.models import Observation


def make_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
        location_text='Bay 1',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


def make_observation(unit, **kwargs):
    defaults = dict(
        tracking_unit=unit,
        observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
        status=Observation.STATUS_HEALTHY,
    )
    defaults.update(kwargs)
    return Observation.objects.create(**defaults)


class DashboardIndexTest(TestCase):

    def test_index_returns_200(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_shows_total_active_unit_count(self):
        make_unit('TU-D-001')
        make_unit('TU-D-002')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['total_units'], 2)

    def test_active_unit_appears_in_table(self):
        unit = make_unit('TU-ACTIVE-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, unit.unit_code)

    def test_inactive_unit_excluded_from_table(self):
        active = make_unit('TU-ACT-001')
        inactive = make_unit('TU-INACT-001', is_active=False)
        response = self.client.get('/dashboard/')
        self.assertContains(response, active.unit_code)
        self.assertNotContains(response, inactive.unit_code)

    def test_shows_unit_code_in_table(self):
        make_unit('TU-CODE-TEST-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'TU-CODE-TEST-001')

    def test_shows_crop_name_in_table(self):
        make_unit('TU-CROP-001', crop_name='Baobab Tree')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Baobab Tree')

    def test_shows_quantity_in_table(self):
        make_unit('TU-QTY-001', quantity=55)
        response = self.client.get('/dashboard/')
        self.assertContains(response, '55')

    def test_shows_location_text_in_table(self):
        make_unit('TU-LOC-001', location_text='Bay 7 North')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Bay 7 North')

    def test_shows_latest_observation_status_when_present(self):
        unit = make_unit('TU-STATUS-001')
        make_observation(unit, status=Observation.STATUS_SICK)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Sick')

    def test_shows_not_checked_when_no_observation(self):
        make_unit('TU-NOOBS-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Not checked')

    def test_includes_qr_label_link(self):
        unit = make_unit('TU-QRL-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/qr/units/{unit.unit_code}/label/')

    def test_includes_observe_link(self):
        unit = make_unit('TU-OBS-LNK-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/observe/{unit.unit_code}/')

    def test_includes_timeline_link(self):
        unit = make_unit('TU-TL-LNK-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/observe/{unit.unit_code}/timeline/')

    def test_counts_units_with_and_without_qr(self):
        make_unit('TU-NQRC-001')
        make_unit('TU-NQRC-002')
        qr_unit = make_unit('TU-YQRC-001')
        # Set qr_code path directly without needing a real image file
        TrackingUnit.objects.filter(pk=qr_unit.pk).update(qr_code='qr_codes/test.png')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['units_with_qr'], 1)
        self.assertEqual(response.context['units_without_qr'], 2)

    def test_counts_units_checked_today(self):
        checked = make_unit('TU-TODAY-001')
        make_unit('TU-UNTODAY-001')
        make_observation(checked, status=Observation.STATUS_HEALTHY)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['units_checked_today'], 1)
