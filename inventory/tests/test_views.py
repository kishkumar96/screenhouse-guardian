from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

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


# ── Helper ────────────────────────────────────────────────────────────────────

def make_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Archive Test Crop',
        quantity=5,
        location_text='Bay A',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


# ── /inventory/units/<unit_code>/archive/ — access ───────────────────────────

class ArchiveUnitAccessTest(TestCase):

    def setUp(self):
        self.observer = make_observer('arch_obs')
        self.manager = make_manager('arch_mgr')
        self.unit = make_unit('TU-ARCH-ACC-001')

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_403(self):
        self.client.login(username='arch_obs', password=PASSWORD)
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertEqual(response.status_code, 403)

    def test_manager_gets_200(self):
        self.client.login(username='arch_mgr', password=PASSWORD)
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertEqual(response.status_code, 200)

    def test_missing_unit_returns_404(self):
        self.client.login(username='arch_mgr', password=PASSWORD)
        response = self.client.get('/inventory/units/NO-SUCH-UNIT/archive/')
        self.assertEqual(response.status_code, 404)


# ── /inventory/units/<unit_code>/archive/ — display ─────────────────────────

class ArchiveUnitDisplayTest(TestCase):

    def setUp(self):
        make_manager('arch_disp_mgr')
        self.client.login(username='arch_disp_mgr', password=PASSWORD)
        self.unit = make_unit(
            'TU-ARCH-DISP-001',
            crop_name='Display Archive Crop',
            location_text='Bay D',
        )

    def test_shows_unit_code(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, self.unit.unit_code)

    def test_shows_crop(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, 'Display Archive Crop')

    def test_shows_location(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, 'Bay D')

    def test_shows_archive_reason_field(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, 'archive_reason')

    def test_shows_confirm_field(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, 'confirm')

    def test_shows_warning_text(self):
        response = self.client.get(f'/inventory/units/{self.unit.unit_code}/archive/')
        self.assertContains(response, 'active dashboard')


# ── /inventory/units/<unit_code>/archive/ — POST behaviour ──────────────────

class ArchiveUnitPostTest(TestCase):

    def setUp(self):
        make_manager('arch_post_mgr')
        self.client.login(username='arch_post_mgr', password=PASSWORD)
        self.unit = make_unit('TU-ARCH-POST-001')

    def _post(self, data=None):
        base = {'archive_reason': 'dead', 'confirm': 'on'}
        if data:
            base.update(data)
        return self.client.post(
            f'/inventory/units/{self.unit.unit_code}/archive/',
            base,
        )

    def test_valid_post_sets_is_active_false(self):
        self._post()
        self.unit.refresh_from_db()
        self.assertFalse(self.unit.is_active)

    def test_valid_post_sets_archived_at(self):
        before = timezone.now()
        self._post()
        self.unit.refresh_from_db()
        self.assertIsNotNone(self.unit.archived_at)
        self.assertGreaterEqual(self.unit.archived_at, before)

    def test_valid_post_sets_archive_reason(self):
        self._post({'archive_reason': 'empty', 'confirm': 'on'})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.archive_reason, 'empty')

    def test_valid_post_redirects_to_timeline(self):
        response = self._post()
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )

    def test_valid_post_shows_success_message(self):
        self._post()
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'archived')

    def test_missing_archive_reason_keeps_unit_active(self):
        response = self.client.post(
            f'/inventory/units/{self.unit.unit_code}/archive/',
            {'confirm': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.is_active)

    def test_missing_confirm_keeps_unit_active(self):
        response = self.client.post(
            f'/inventory/units/{self.unit.unit_code}/archive/',
            {'archive_reason': 'dead'},
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.is_active)

    def test_already_archived_unit_redirects_with_info(self):
        self.unit.is_active = False
        self.unit.archived_at = timezone.now()
        self.unit.archive_reason = 'dead'
        self.unit.save(update_fields=['is_active', 'archived_at', 'archive_reason'])
        response = self._post()
        self.assertEqual(response.status_code, 302)

    def test_anonymous_post_redirects_to_login(self):
        self.client.logout()
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_post_gets_403(self):
        make_observer('arch_obs_post')
        self.client.login(username='arch_obs_post', password=PASSWORD)
        response = self._post()
        self.assertEqual(response.status_code, 403)
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.is_active)


# ── /inventory/archived-units/ — access ─────────────────────────────────────

class ArchivedUnitsListAccessTest(TestCase):

    def test_anonymous_redirects_to_login(self):
        response = self.client.get('/inventory/archived-units/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_200(self):
        make_observer('arch_list_obs')
        self.client.login(username='arch_list_obs', password=PASSWORD)
        response = self.client.get('/inventory/archived-units/')
        self.assertEqual(response.status_code, 200)

    def test_manager_gets_200(self):
        make_manager('arch_list_mgr')
        self.client.login(username='arch_list_mgr', password=PASSWORD)
        response = self.client.get('/inventory/archived-units/')
        self.assertEqual(response.status_code, 200)


# ── /inventory/archived-units/ — content ────────────────────────────────────

class ArchivedUnitsListContentTest(TestCase):

    def setUp(self):
        make_observer('arch_cnt_obs')
        self.client.login(username='arch_cnt_obs', password=PASSWORD)

    def test_lists_archived_unit(self):
        unit = make_unit('TU-ARCH-LIST-001', is_active=False, archive_reason='dead')
        TrackingUnit.objects.filter(pk=unit.pk).update(archived_at=timezone.now())
        response = self.client.get('/inventory/archived-units/')
        self.assertContains(response, 'TU-ARCH-LIST-001')

    def test_does_not_list_active_unit(self):
        make_unit('TU-ACTIVE-NOTLIST-001')
        response = self.client.get('/inventory/archived-units/')
        self.assertNotContains(response, 'TU-ACTIVE-NOTLIST-001')

    def test_shows_archive_reason(self):
        unit = make_unit('TU-ARCH-RSN-001', is_active=False, archive_reason='empty')
        TrackingUnit.objects.filter(pk=unit.pk).update(archived_at=timezone.now())
        response = self.client.get('/inventory/archived-units/')
        self.assertContains(response, 'Empty')

    def test_includes_timeline_link(self):
        unit = make_unit('TU-ARCH-TL-001', is_active=False, archive_reason='retired')
        TrackingUnit.objects.filter(pk=unit.pk).update(archived_at=timezone.now())
        response = self.client.get('/inventory/archived-units/')
        self.assertContains(response, f'/observe/{unit.unit_code}/timeline/')
