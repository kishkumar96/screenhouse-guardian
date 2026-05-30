from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from inventory.models import Accession, Batch, Crop, TrackingUnit

PASSWORD = 'testpass123'


def make_observer(username='inv_observer'):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD)
    group, _ = Group.objects.get_or_create(name='Observer')
    user.groups.add(group)
    return user


def make_manager(username='inv_manager'):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD)
    group, _ = Group.objects.get_or_create(name='Manager')
    user.groups.add(group)
    return user


# ── /inventory/ ───────────────────────────────────────────────────────────────

class InventoryIndexTest(TestCase):
    def test_index_redirects_anonymous_user_to_login(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_index_returns_200_for_observer(self):
        make_observer()
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)

    def test_index_shows_crop_count(self):
        make_observer()
        self.client.login(username='inv_observer', password=PASSWORD)
        Crop.objects.create(name='Count Crop')
        response = self.client.get('/inventory/')
        self.assertEqual(response.context['crop_count'], 1)

    def test_index_shows_accession_count(self):
        make_observer()
        self.client.login(username='inv_observer', password=PASSWORD)
        crop = Crop.objects.create(name='Acc Count Crop')
        Accession.objects.create(crop=crop, accession_code='ACC-CNT-001')
        response = self.client.get('/inventory/')
        self.assertEqual(response.context['accession_count'], 1)

    def test_index_shows_links_to_crop_accession_batch(self):
        make_observer()
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/')
        self.assertContains(response, '/inventory/crops/')
        self.assertContains(response, '/inventory/accessions/')
        self.assertContains(response, '/inventory/batches/')


# ── /inventory/crops/ ─────────────────────────────────────────────────────────

class CropListViewTest(TestCase):

    def setUp(self):
        self.observer = make_observer()
        self.manager = make_manager()

    def test_redirects_anonymous(self):
        response = self.client.get('/inventory/crops/')
        self.assertIn('/accounts/login/', response['Location'])

    def test_returns_200_for_observer(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertEqual(response.status_code, 200)

    def test_shows_existing_crops(self):
        Crop.objects.create(name='Existing Taro')
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertContains(response, 'Existing Taro')

    def test_observer_sees_no_create_form(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertIsNone(response.context['form'])

    def test_manager_sees_create_form(self):
        self.client.login(username='inv_manager', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertIsNotNone(response.context['form'])

    def test_manager_can_create_crop(self):
        self.client.login(username='inv_manager', password=PASSWORD)
        response = self.client.post('/inventory/crops/', {
            'name': 'New Cassava',
            'scientific_name': '',
            'category': '',
            'notes': '',
        })
        self.assertRedirects(response, '/inventory/crops/', fetch_redirect_response=False)
        self.assertTrue(Crop.objects.filter(name='New Cassava').exists())

    def test_observer_cannot_create_crop_via_post(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.post('/inventory/crops/', {
            'name': 'Forbidden Crop',
            'scientific_name': '',
            'category': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Crop.objects.filter(name='Forbidden Crop').exists())

    def test_invalid_form_shows_errors(self):
        self.client.login(username='inv_manager', password=PASSWORD)
        # Duplicate name
        Crop.objects.create(name='Dupe Crop')
        response = self.client.post('/inventory/crops/', {
            'name': 'Dupe Crop',
            'scientific_name': '',
            'category': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Crop.objects.filter(name='Dupe Crop').count() > 1)

    def test_shows_accession_and_unit_counts(self):
        crop = Crop.objects.create(name='Counted Crop')
        Accession.objects.create(crop=crop, accession_code='CNT-ACC-001')
        TrackingUnit.objects.create(
            unit_code='TU-CNT-001',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Counted Crop',
            crop=crop,
        )
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertEqual(response.status_code, 200)
        counted = next(c for c in response.context['crops'] if c.name == 'Counted Crop')
        self.assertEqual(counted.accession_count, 1)
        self.assertEqual(counted.unit_count, 1)

    def test_back_link_to_inventory_index(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/crops/')
        self.assertContains(response, '/inventory/')


# ── /inventory/accessions/ ────────────────────────────────────────────────────

class AccessionListViewTest(TestCase):

    def setUp(self):
        self.observer = make_observer()
        self.manager = make_manager()
        self.crop = Crop.objects.create(name='Taro For Acc')

    def test_returns_200_for_observer(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/accessions/')
        self.assertEqual(response.status_code, 200)

    def test_shows_existing_accessions(self):
        Accession.objects.create(crop=self.crop, accession_code='SHOW-ACC-001')
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/accessions/')
        self.assertContains(response, 'SHOW-ACC-001')

    def test_observer_sees_no_create_form(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/accessions/')
        self.assertIsNone(response.context['form'])

    def test_manager_can_create_accession(self):
        self.client.login(username='inv_manager', password=PASSWORD)
        response = self.client.post('/inventory/accessions/', {
            'crop': self.crop.pk,
            'accession_code': 'NEW-ACC-001',
            'source_country': 'Fiji',
            'source_organisation': '',
            'notes': '',
        })
        self.assertRedirects(response, '/inventory/accessions/', fetch_redirect_response=False)
        self.assertTrue(Accession.objects.filter(accession_code='NEW-ACC-001').exists())

    def test_observer_cannot_create_accession(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.post('/inventory/accessions/', {
            'crop': self.crop.pk,
            'accession_code': 'FORBIDDEN-ACC',
            'source_country': '',
            'source_organisation': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 403)

    def test_shows_crop_name_in_table(self):
        Accession.objects.create(crop=self.crop, accession_code='CROP-ACC-001')
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/accessions/')
        self.assertContains(response, 'Taro For Acc')

    def test_redirects_anonymous(self):
        response = self.client.get('/inventory/accessions/')
        self.assertEqual(response.status_code, 302)


# ── /inventory/batches/ ───────────────────────────────────────────────────────

class BatchListViewTest(TestCase):

    def setUp(self):
        self.observer = make_observer()
        self.manager = make_manager()
        crop = Crop.objects.create(name='Batch Crop')
        self.accession = Accession.objects.create(crop=crop, accession_code='BCH-ACC-001')

    def test_returns_200_for_observer(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/batches/')
        self.assertEqual(response.status_code, 200)

    def test_shows_existing_batches(self):
        Batch.objects.create(accession=self.accession, batch_code='SHOW-BCH-001')
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/batches/')
        self.assertContains(response, 'SHOW-BCH-001')

    def test_observer_sees_no_create_form(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/batches/')
        self.assertIsNone(response.context['form'])

    def test_manager_can_create_batch(self):
        self.client.login(username='inv_manager', password=PASSWORD)
        response = self.client.post('/inventory/batches/', {
            'accession': self.accession.pk,
            'batch_code': 'NEW-BCH-001',
            'source_type': 'seedling',
            'received_date': '',
            'initial_quantity': 10,
            'notes': '',
        })
        self.assertRedirects(response, '/inventory/batches/', fetch_redirect_response=False)
        self.assertTrue(Batch.objects.filter(batch_code='NEW-BCH-001').exists())

    def test_observer_cannot_create_batch(self):
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.post('/inventory/batches/', {
            'accession': self.accession.pk,
            'batch_code': 'FORBIDDEN-BCH',
            'source_type': '',
            'received_date': '',
            'initial_quantity': 0,
            'notes': '',
        })
        self.assertEqual(response.status_code, 403)

    def test_shows_accession_and_crop_in_table(self):
        Batch.objects.create(accession=self.accession, batch_code='TABLE-BCH-001')
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/batches/')
        self.assertContains(response, 'BCH-ACC-001')
        self.assertContains(response, 'Batch Crop')

    def test_redirects_anonymous(self):
        response = self.client.get('/inventory/batches/')
        self.assertEqual(response.status_code, 302)
