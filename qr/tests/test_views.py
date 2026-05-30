import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from inventory.models import TrackingUnit

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

    def test_missing_unit_returns_404(self):
        response = self.client.get('/qr/units/UNIT-DOES-NOT-EXIST/label/')
        self.assertEqual(response.status_code, 404)


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
