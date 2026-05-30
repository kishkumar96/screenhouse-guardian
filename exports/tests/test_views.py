import csv
import tempfile
from io import BytesIO, StringIO

from django.test import TestCase, override_settings

from inventory.models import TrackingUnit
from monitoring.models import Observation, ObservationPhoto, QuantityEvent

_XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


# ── Shared helpers ────────────────────────────────────────────────────────────

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


def make_quantity_event(unit, quantity_change=-2, **kwargs):
    before = unit.quantity
    after = before + quantity_change
    defaults = dict(
        tracking_unit=unit,
        event_type=QuantityEvent.EVENT_TYPE_DEATH,
        quantity_before=before,
        quantity_change=quantity_change,
        quantity_after=after,
    )
    defaults.update(kwargs)
    event = QuantityEvent.objects.create(**defaults)
    unit.quantity = after
    unit.save(update_fields=['quantity'])
    return event


def create_test_jpeg():
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    img = Image.new('RGB', (10, 10), color='green')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('plant.jpg', buf.read(), content_type='image/jpeg')


def csv_headers(response):
    reader = csv.reader(StringIO(response.content.decode()))
    return next(reader)


# ── Export index ──────────────────────────────────────────────────────────────

class ExportIndexTest(TestCase):

    def test_index_returns_200(self):
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 200)

    def test_index_contains_csv_links(self):
        response = self.client.get('/exports/')
        for path in [
            '/exports/tracking-units.csv/',
            '/exports/observations.csv/',
            '/exports/quantity-events.csv/',
            '/exports/photo-metadata.csv/',
        ]:
            self.assertContains(response, path)

    def test_index_contains_excel_links(self):
        response = self.client.get('/exports/')
        for path in [
            '/exports/tracking-units.xlsx/',
            '/exports/observations.xlsx/',
            '/exports/quantity-events.xlsx/',
            '/exports/photo-metadata.xlsx/',
        ]:
            self.assertContains(response, path)


# ── Tracking units CSV ────────────────────────────────────────────────────────

class TrackingUnitsCsvTest(TestCase):

    def test_returns_200(self):
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertEqual(response.status_code, 200)

    def test_content_type_is_csv(self):
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertIn('text/csv', response['Content-Type'])

    def test_has_expected_header_columns(self):
        headers = csv_headers(self.client.get('/exports/tracking-units.csv/'))
        for col in ['unit_code', 'unit_type', 'crop_name', 'quantity',
                    'location_text', 'has_qr_code', 'is_active', 'created_at']:
            self.assertIn(col, headers)

    def test_includes_unit_code_and_crop_name(self):
        make_unit('TU-EXP-001', crop_name='Baobab Export')
        response = self.client.get('/exports/tracking-units.csv/')
        content = response.content.decode()
        self.assertIn('TU-EXP-001', content)
        self.assertIn('Baobab Export', content)

    def test_has_attachment_content_disposition(self):
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertIn('tracking_units.csv', response['Content-Disposition'])


# ── Observations CSV ──────────────────────────────────────────────────────────

class ObservationsCsvTest(TestCase):

    def test_returns_200(self):
        response = self.client.get('/exports/observations.csv/')
        self.assertEqual(response.status_code, 200)

    def test_includes_tracking_unit_code_and_status(self):
        unit = make_unit('TU-OBS-EXP-001')
        make_observation(unit, status=Observation.STATUS_SICK)
        response = self.client.get('/exports/observations.csv/')
        content = response.content.decode()
        self.assertIn('TU-OBS-EXP-001', content)
        self.assertIn('sick', content)

    def test_has_expected_header_columns(self):
        headers = csv_headers(self.client.get('/exports/observations.csv/'))
        for col in ['tracking_unit_code', 'observation_type', 'status', 'created_at']:
            self.assertIn(col, headers)


# ── Quantity events CSV ───────────────────────────────────────────────────────

class QuantityEventsCsvTest(TestCase):

    def setUp(self):
        self.unit = make_unit('TU-QE-EXP-001', quantity=20)

    def test_returns_200(self):
        response = self.client.get('/exports/quantity-events.csv/')
        self.assertEqual(response.status_code, 200)

    def test_header_includes_quantity_columns(self):
        headers = csv_headers(self.client.get('/exports/quantity-events.csv/'))
        self.assertIn('quantity_before', headers)
        self.assertIn('quantity_change', headers)
        self.assertIn('quantity_after', headers)

    def test_includes_event_data(self):
        make_quantity_event(self.unit, quantity_change=-3)
        response = self.client.get('/exports/quantity-events.csv/')
        content = response.content.decode()
        self.assertIn('TU-QE-EXP-001', content)
        self.assertIn('20', content)   # quantity_before
        self.assertIn('-3', content)   # quantity_change


# ── Photo metadata CSV ────────────────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoMetadataCsvTest(TestCase):

    def setUp(self):
        unit = make_unit('TU-PH-EXP-001', quantity=5)
        obs = make_observation(unit, status=Observation.STATUS_HEALTHY)
        ObservationPhoto.objects.create(
            observation=obs,
            image=create_test_jpeg(),
            caption='Export test photo',
        )

    def test_returns_200(self):
        response = self.client.get('/exports/photo-metadata.csv/')
        self.assertEqual(response.status_code, 200)

    def test_includes_image_path(self):
        response = self.client.get('/exports/photo-metadata.csv/')
        content = response.content.decode()
        self.assertIn('TU-PH-EXP-001', content)
        self.assertIn('observation_photos', content)

    def test_includes_caption(self):
        response = self.client.get('/exports/photo-metadata.csv/')
        self.assertIn('Export test photo', response.content.decode())

    def test_has_expected_header_columns(self):
        headers = csv_headers(self.client.get('/exports/photo-metadata.csv/'))
        for col in ['tracking_unit_code', 'observation_id', 'image_name',
                    'image_url_or_path', 'caption', 'uploaded_at']:
            self.assertIn(col, headers)


# ── Excel exports ─────────────────────────────────────────────────────────────

class ExcelExportTest(TestCase):

    def test_tracking_units_excel_returns_200(self):
        response = self.client.get('/exports/tracking-units.xlsx/')
        self.assertEqual(response.status_code, 200)

    def test_observations_excel_returns_200(self):
        response = self.client.get('/exports/observations.xlsx/')
        self.assertEqual(response.status_code, 200)

    def test_quantity_events_excel_returns_200(self):
        response = self.client.get('/exports/quantity-events.xlsx/')
        self.assertEqual(response.status_code, 200)

    def test_photo_metadata_excel_returns_200(self):
        response = self.client.get('/exports/photo-metadata.xlsx/')
        self.assertEqual(response.status_code, 200)

    def test_excel_response_has_correct_content_type(self):
        response = self.client.get('/exports/tracking-units.xlsx/')
        self.assertEqual(response['Content-Type'], _XLSX_CONTENT_TYPE)

    def test_excel_response_has_attachment_filename(self):
        response = self.client.get('/exports/tracking-units.xlsx/')
        self.assertIn('tracking_units.xlsx', response['Content-Disposition'])

    def test_observations_excel_has_correct_content_type(self):
        response = self.client.get('/exports/observations.xlsx/')
        self.assertEqual(response['Content-Type'], _XLSX_CONTENT_TYPE)

    def test_quantity_events_excel_has_correct_content_type(self):
        response = self.client.get('/exports/quantity-events.xlsx/')
        self.assertEqual(response['Content-Type'], _XLSX_CONTENT_TYPE)

    def test_photo_metadata_excel_has_correct_content_type(self):
        response = self.client.get('/exports/photo-metadata.xlsx/')
        self.assertEqual(response['Content-Type'], _XLSX_CONTENT_TYPE)
