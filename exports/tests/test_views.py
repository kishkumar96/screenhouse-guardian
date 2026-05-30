import csv
import tempfile
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from inventory.models import (
    Accession, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)
from monitoring.models import Observation, ObservationPhoto, QuantityEvent

User = get_user_model()

_XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
_PASSWORD = 'testpass123'


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_manager(username='exp_manager'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Manager')
    user.groups.add(group)
    return user


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

def make_observer(username='exp_observer'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Observer')
    user.groups.add(group)
    return user


class ExportIndexTest(TestCase):

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)

    def test_index_returns_200(self):
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 200)

    def test_index_returns_403_for_observer(self):
        make_observer()
        self.client.login(username='exp_observer', password=_PASSWORD)
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 403)

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

    def test_index_contains_export_descriptions(self):
        response = self.client.get('/exports/')
        self.assertContains(response, 'One row per tracking unit')
        self.assertContains(response, 'One row per observation')
        self.assertContains(response, 'One row per quantity change')
        self.assertContains(response, 'One row per uploaded photo')


# ── Tracking units CSV ────────────────────────────────────────────────────────

class TrackingUnitsCsvTest(TestCase):

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)

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

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)

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
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)
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
        self.assertIn('20', content)
        self.assertIn('-3', content)


# ── Photo metadata CSV ────────────────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PhotoMetadataCsvTest(TestCase):

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)
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

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='exp_manager', password=_PASSWORD)

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


# ── Phase 1B: structured columns in tracking units export ─────────────────────

class TrackingUnitsStructuredColumnsTest(TestCase):

    def setUp(self):
        self.user = make_manager('exp_struct_mgr')
        self.client.login(username='exp_struct_mgr', password=_PASSWORD)

    def test_csv_has_structured_column_headers(self):
        headers = csv_headers(self.client.get('/exports/tracking-units.csv/'))
        for col in ['structured_crop', 'structured_accession', 'structured_batch', 'structured_location']:
            self.assertIn(col, headers)

    def test_csv_still_has_legacy_column_headers(self):
        headers = csv_headers(self.client.get('/exports/tracking-units.csv/'))
        for col in ['crop_name', 'accession_code', 'batch_code', 'location_text']:
            self.assertIn(col, headers)

    def test_csv_structured_crop_populated_when_fk_linked(self):
        crop = Crop.objects.create(name='Export Cassava')
        make_unit('TU-STRUCT-001', crop_name='Legacy Cassava', crop=crop)
        response = self.client.get('/exports/tracking-units.csv/')
        content = response.content.decode()
        self.assertIn('Export Cassava', content)
        self.assertIn('Legacy Cassava', content)

    def test_csv_structured_crop_empty_when_no_fk(self):
        make_unit('TU-STRUCT-002', crop_name='Only Legacy Crop')
        response = self.client.get('/exports/tracking-units.csv/')
        reader = csv.reader(StringIO(response.content.decode()))
        headers = next(reader)
        struct_crop_idx = headers.index('structured_crop')
        for row in reader:
            if row and 'TU-STRUCT-002' in row[0]:
                self.assertEqual(row[struct_crop_idx], '')

    def test_csv_structured_location_populated_when_position_linked(self):
        site, _ = Site.objects.get_or_create(name='Export Site')
        sh, _ = ScreenHouse.objects.get_or_create(site=site, name='ESH1')
        bench, _ = Bench.objects.get_or_create(screen_house=sh, name='EBench A')
        pos, _ = Position.objects.get_or_create(bench=bench, code='EP1')
        make_unit('TU-STRUCT-003', location_text='Old location', position=pos)
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertIn('Export Site / ESH1 / EBench A / EP1', response.content.decode())

    def test_tracking_units_excel_returns_200_with_structured_columns(self):
        crop = Crop.objects.create(name='Excel Cassava')
        make_unit('TU-STRUCT-XL-001', crop_name='Excel Cassava', crop=crop)
        response = self.client.get('/exports/tracking-units.xlsx/')
        self.assertEqual(response.status_code, 200)
