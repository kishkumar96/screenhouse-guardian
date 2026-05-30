import tempfile

from django.test import RequestFactory, TestCase, override_settings

from inventory.models import TrackingUnit
from qr.services import build_observation_url, generate_qr_for_tracking_unit


def make_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


class BuildObservationUrlTest(TestCase):

    def test_url_contains_unit_code(self):
        unit = make_unit('TU-URL-CODE-001')
        url = build_observation_url(unit, base_url='https://example.com')
        self.assertIn('TU-URL-CODE-001', url)

    def test_uses_base_url(self):
        unit = make_unit('TU-URL-BASE-001')
        url = build_observation_url(unit, base_url='https://example.com')
        self.assertEqual(url, 'https://example.com/observe/TU-URL-BASE-001/')

    def test_base_url_trailing_slash_stripped(self):
        unit = make_unit('TU-URL-BASE-002')
        url = build_observation_url(unit, base_url='https://example.com/')
        self.assertEqual(url, 'https://example.com/observe/TU-URL-BASE-002/')

    def test_uses_request_build_absolute_uri(self):
        unit = make_unit('TU-URL-REQ-001')
        factory = RequestFactory()
        request = factory.get('/')
        url = build_observation_url(unit, request=request)
        self.assertIn('/observe/TU-URL-REQ-001/', url)
        self.assertTrue(url.startswith('http'))

    def test_request_takes_priority_over_base_url(self):
        unit = make_unit('TU-URL-PRIO-001')
        factory = RequestFactory()
        request = factory.get('/')
        url = build_observation_url(unit, request=request, base_url='https://ignored.example.com')
        # request.build_absolute_uri uses testserver, not the base_url
        self.assertIn('testserver', url)

    def test_without_request_or_base_url_returns_relative_path(self):
        unit = make_unit('TU-URL-REL-001')
        url = build_observation_url(unit)
        self.assertEqual(url, '/observe/TU-URL-REL-001/')

    def test_url_is_stable_across_calls(self):
        unit = make_unit('TU-URL-STABLE-001')
        url1 = build_observation_url(unit, base_url='https://example.com')
        url2 = build_observation_url(unit, base_url='https://example.com')
        self.assertEqual(url1, url2)

    def test_observe_path_format(self):
        unit = make_unit('TU-CAS-0001')
        url = build_observation_url(unit, base_url='http://127.0.0.1:8000')
        self.assertEqual(url, 'http://127.0.0.1:8000/observe/TU-CAS-0001/')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerateQrServiceTest(TestCase):

    def test_generate_saves_qr_code_to_tracking_unit(self):
        unit = make_unit('TU-GEN-SVC-001')
        self.assertFalse(unit.qr_code)

        generate_qr_for_tracking_unit(unit, base_url='https://example.com')

        unit.refresh_from_db()
        self.assertTrue(unit.qr_code)

    def test_generate_returns_tracking_unit(self):
        unit = make_unit('TU-GEN-SVC-002')
        result = generate_qr_for_tracking_unit(unit, base_url='https://example.com')
        self.assertIsInstance(result, TrackingUnit)
        self.assertEqual(result.pk, unit.pk)

    def test_generate_does_not_create_new_tracking_unit(self):
        unit = make_unit('TU-GEN-SVC-003')
        count_before = TrackingUnit.objects.count()

        generate_qr_for_tracking_unit(unit, base_url='https://example.com')

        self.assertEqual(TrackingUnit.objects.count(), count_before)

    def test_regenerate_does_not_create_new_tracking_unit(self):
        unit = make_unit('TU-GEN-SVC-004')
        generate_qr_for_tracking_unit(unit, base_url='https://example.com')
        count_before = TrackingUnit.objects.count()

        generate_qr_for_tracking_unit(unit, base_url='https://example.com')

        self.assertEqual(TrackingUnit.objects.count(), count_before)

    def test_regenerate_keeps_same_unit_code(self):
        unit = make_unit('TU-GEN-SVC-005')
        generate_qr_for_tracking_unit(unit, base_url='https://example.com')
        generate_qr_for_tracking_unit(unit, base_url='https://example.com')

        unit.refresh_from_db()
        self.assertEqual(unit.unit_code, 'TU-GEN-SVC-005')
        self.assertTrue(unit.qr_code)

    def test_qr_code_filename_contains_unit_code(self):
        unit = make_unit('TU-GEN-SVC-006')
        generate_qr_for_tracking_unit(unit, base_url='https://example.com')
        unit.refresh_from_db()
        self.assertIn('TU-GEN-SVC-006', unit.qr_code.name)

    def test_generate_with_request(self):
        unit = make_unit('TU-GEN-SVC-REQ-001')
        factory = RequestFactory()
        request = factory.get('/')

        generate_qr_for_tracking_unit(unit, request=request)

        unit.refresh_from_db()
        self.assertTrue(unit.qr_code)
