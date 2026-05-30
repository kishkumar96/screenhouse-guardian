import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from inventory.models import (
    Accession, Batch, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)

User = get_user_model()

_PASSWORD = 'testpass123'


def make_user(username, group_name=None):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


def make_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='View Test Crop',
        quantity=5,
        location_text='Screen House A',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


class QrIndexTest(TestCase):

    def test_index_returns_200(self):
        response = self.client.get('/qr/')
        self.assertEqual(response.status_code, 200)


class LabelViewTest(TestCase):

    def setUp(self):
        self.user = make_user('qr_observer', 'Observer')
        self.client.login(username='qr_observer', password=_PASSWORD)
        self.unit = make_unit(
            'TU-LABEL-001',
            crop_name='Baobab',
            accession_code='ACC-001',
            batch_code='BATCH-A',
            location_text='Bay 3',
            quantity=12,
        )

    def test_label_returns_200(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertEqual(response.status_code, 200)

    def test_label_contains_unit_code(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, self.unit.unit_code)

    def test_label_contains_crop_name(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, self.unit.crop_name)

    def test_label_contains_quantity(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, str(self.unit.quantity))

    def test_label_contains_location_text(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, self.unit.location_text)

    def test_label_contains_scan_instruction(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, 'Scan to update status')

    def test_label_contains_accession_code(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, self.unit.accession_code)

    def test_label_contains_back_to_dashboard_link(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, '/dashboard/')

    def test_missing_unit_returns_404(self):
        response = self.client.get('/qr/units/UNIT-DOES-NOT-EXIST/label/')
        self.assertEqual(response.status_code, 404)

    def test_generate_button_hidden_from_observer(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertNotContains(response, 'Generate QR Code')
        self.assertNotContains(response, 'Regenerate QR Code')

    def test_generate_button_visible_to_manager(self):
        manager = make_user('qr_label_mgr', 'Manager')
        self.client.login(username='qr_label_mgr', password=_PASSWORD)
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertContains(response, 'Generate QR Code')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GenerateViewTest(TestCase):

    def setUp(self):
        self.user = make_user('qr_manager', 'Manager')
        self.client.login(username='qr_manager', password=_PASSWORD)
        self.unit = make_unit('TU-GENVIEW-001')

    def test_generate_creates_qr_code(self):
        self.assertFalse(self.unit.qr_code)

        self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')

        self.unit.refresh_from_db()
        self.assertTrue(self.unit.qr_code)

    def test_generate_redirects_to_label(self):
        response = self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')
        self.assertRedirects(
            response,
            f'/qr/units/{self.unit.unit_code}/label/',
            fetch_redirect_response=False,
        )

    def test_generate_redirects_to_next_when_provided(self):
        response = self.client.post(
            f'/qr/units/{self.unit.unit_code}/generate/',
            data={'next': '/dashboard/'},
        )
        self.assertRedirects(
            response,
            '/dashboard/',
            fetch_redirect_response=False,
        )

    def test_generate_ignores_unsafe_next_url(self):
        response = self.client.post(
            f'/qr/units/{self.unit.unit_code}/generate/',
            data={'next': 'https://evil.example.com/'},
        )
        self.assertRedirects(
            response,
            f'/qr/units/{self.unit.unit_code}/label/',
            fetch_redirect_response=False,
        )

    def test_regenerate_updates_qr_and_unit_survives(self):
        self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')
        self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')

        self.unit.refresh_from_db()
        self.assertTrue(self.unit.qr_code)
        self.assertEqual(self.unit.unit_code, 'TU-GENVIEW-001')

    def test_generate_missing_unit_returns_404(self):
        response = self.client.post('/qr/units/NO-SUCH-UNIT/generate/')
        self.assertEqual(response.status_code, 404)

    def test_generate_get_returns_405(self):
        # GET is not allowed even for managers
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/generate/')
        self.assertEqual(response.status_code, 405)


# ── Phase 1B: QR label uses display helpers ───────────────────────────────────

class LabelDisplayPropertiesTest(TestCase):

    def setUp(self):
        self.user = make_user('qr_disp_obs', 'Observer')
        self.client.login(username='qr_disp_obs', password=_PASSWORD)

    def test_label_shows_structured_crop_when_fk_linked(self):
        crop = Crop.objects.create(name='Structured Taro')
        unit = make_unit('TU-QD-001', crop_name='Old Taro', crop=crop)
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'Structured Taro')

    def test_label_falls_back_to_crop_name_when_no_fk(self):
        unit = make_unit('TU-QD-002', crop_name='Legacy Taro')
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'Legacy Taro')

    def test_label_shows_structured_accession_when_fk_linked(self):
        crop = Crop.objects.create(name='QD Crop')
        acc = Accession.objects.create(crop=crop, accession_code='QD-ACC-STRUCT')
        unit = make_unit('TU-QD-003', crop_name='QD Crop', accession_code='OLD-ACC', accession=acc)
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'QD-ACC-STRUCT')

    def test_label_falls_back_to_accession_code_when_no_fk(self):
        unit = make_unit('TU-QD-004', accession_code='LEGACY-QD-ACC')
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'LEGACY-QD-ACC')

    def test_label_shows_structured_location_when_position_linked(self):
        site, _ = Site.objects.get_or_create(name='QD Site')
        sh, _ = ScreenHouse.objects.get_or_create(site=site, name='QDSH1')
        bench, _ = Bench.objects.get_or_create(screen_house=sh, name='QD Bench')
        pos, _ = Position.objects.get_or_create(bench=bench, code='QDP1')
        unit = make_unit('TU-QD-005', location_text='Old location', position=pos)
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'QD Site / QDSH1 / QD Bench / QDP1')

    def test_label_falls_back_to_location_text_when_no_position_fk(self):
        unit = make_unit('TU-QD-006', location_text='Legacy Bay X')
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'Legacy Bay X')

    def test_label_shows_structured_batch_when_fk_linked(self):
        crop = Crop.objects.create(name='QD Batch Crop')
        acc = Accession.objects.create(crop=crop, accession_code='QD-BCH-ACC')
        batch = Batch.objects.create(accession=acc, batch_code='QD-BCH-STRUCT')
        unit = make_unit('TU-QD-007', crop_name='QD Batch Crop', batch_code='OLD-BCH', batch=batch)
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'QD-BCH-STRUCT')

    def test_label_falls_back_to_batch_code_when_no_fk(self):
        unit = make_unit('TU-QD-008', batch_code='LEGACY-QD-BCH')
        response = self.client.get(f'/qr/units/{unit.unit_code}/label/')
        self.assertContains(response, 'LEGACY-QD-BCH')
