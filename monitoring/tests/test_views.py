import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

import datetime

from inventory.models import TrackingUnit
from monitoring.models import MAX_OBSERVATION_IMAGE_SIZE_BYTES, Observation, ObservationPhoto, QuantityEvent, Treatment

User = get_user_model()

_PASSWORD = 'testpass123'


# ── Shared helpers ────────────────────────────────────────────────────────────

def make_observer(username='mon_observer'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Observer')
    user.groups.add(group)
    return user


def make_manager(username='mon_manager'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Manager')
    user.groups.add(group)
    return user


def make_unit(unit_code, quantity=10, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        location_text='Bay 1',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, quantity=quantity, **defaults)


def make_observation(unit, **kwargs):
    defaults = dict(
        tracking_unit=unit,
        observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
        status=Observation.STATUS_HEALTHY,
    )
    defaults.update(kwargs)
    return Observation.objects.create(**defaults)


def create_test_jpeg():
    """Return a SimpleUploadedFile containing a valid minimal JPEG."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    img = Image.new('RGB', (10, 10), color='green')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('plant.jpg', buf.read(), content_type='image/jpeg')


def create_oversized_file():
    """Return a SimpleUploadedFile that exceeds the max image upload size."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    content = b'x' * (MAX_OBSERVATION_IMAGE_SIZE_BYTES + 1)
    return SimpleUploadedFile('big.jpg', content, content_type='image/jpeg')


# ── Monitoring index ──────────────────────────────────────────────────────────

class MonitoringIndexTest(TestCase):

    def test_index_redirects_anonymous_user_to_login(self):
        response = self.client.get('/monitoring/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_index_returns_200_for_observer(self):
        user = make_observer()
        self.client.login(username=user.username, password=_PASSWORD)
        response = self.client.get('/monitoring/')
        self.assertEqual(response.status_code, 200)


# ── Observe form — GET ────────────────────────────────────────────────────────

class ObserveFormGetTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-OBS-GET-001', crop_name='Baobab', location_text='Bay 3', quantity=5)

    def test_observe_returns_200(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertEqual(response.status_code, 200)

    def test_observe_contains_unit_code(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, self.unit.unit_code)

    def test_observe_contains_crop_name(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, self.unit.crop_name)

    def test_observe_contains_quantity(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, str(self.unit.quantity))

    def test_observe_contains_location_text(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, self.unit.location_text)

    def test_observe_missing_unit_returns_404(self):
        response = self.client.get('/observe/DOES-NOT-EXIST/')
        self.assertEqual(response.status_code, 404)

    def test_observe_shows_latest_observation_status(self):
        make_observation(self.unit, status=Observation.STATUS_SICK)
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, 'Sick')

    def test_observe_includes_affected_quantity_helper_text(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, 'For containers, enter how many plants are affected')

    def test_observe_includes_photo_helper_text(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, 'Max 5 MB')

    def test_observe_photo_hint_uses_context_mb_value(self):
        from monitoring.models import MAX_OBSERVATION_IMAGE_SIZE_MB
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, f'Max {MAX_OBSERVATION_IMAGE_SIZE_MB} MB')

    def test_observe_photo_hint_mentions_heic(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, 'HEIC')


# ── Observe form — POST, no photo ─────────────────────────────────────────────

class ObserveFormPostTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-OBS-POST-001', quantity=10)

    def _post(self, data=None):
        base = {
            'status': Observation.STATUS_HEALTHY,
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        }
        if data:
            base.update(data)
        return self.client.post(f'/observe/{self.unit.unit_code}/', base)

    def test_valid_post_creates_observation(self):
        self._post()
        self.assertEqual(Observation.objects.filter(tracking_unit=self.unit).count(), 1)

    def test_valid_post_redirects_to_timeline(self):
        response = self._post()
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )

    def test_observation_has_correct_status(self):
        self._post({'status': Observation.STATUS_SICK})
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.status, Observation.STATUS_SICK)

    def test_observation_has_notes(self):
        self._post({'notes': 'Leaves yellowing at edges.'})
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.notes, 'Leaves yellowing at edges.')

    def test_missing_status_does_not_create_observation(self):
        response = self.client.post(f'/observe/{self.unit.unit_code}/', {
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Observation.objects.filter(tracking_unit=self.unit).exists())

    def test_missing_status_shows_form_with_errors(self):
        response = self.client.post(f'/observe/{self.unit.unit_code}/', {
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        self.assertContains(response, 'errorlist')

    def test_affected_quantity_within_limit_accepted(self):
        self._post({'affected_quantity': str(self.unit.quantity)})
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.affected_quantity, self.unit.quantity)

    def test_affected_quantity_exceeding_unit_quantity_rejected(self):
        response = self._post({'affected_quantity': str(self.unit.quantity + 1)})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Observation.objects.filter(tracking_unit=self.unit).exists())

    def test_correction_without_corrects_observation_rejected(self):
        response = self._post({'observation_type': Observation.OBSERVATION_TYPE_CORRECTION})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Observation.objects.filter(tracking_unit=self.unit).exists())

    def test_correction_with_corrects_observation_accepted(self):
        original = make_observation(self.unit, status=Observation.STATUS_SICK)
        self._post({
            'observation_type': Observation.OBSERVATION_TYPE_CORRECTION,
            'corrects_observation': str(original.pk),
            'status': Observation.STATUS_HEALTHY,
        })
        self.assertEqual(Observation.objects.filter(tracking_unit=self.unit).count(), 2)

    def test_anonymous_post_redirects_to_login(self):
        self.client.logout()
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_created_by_is_set_when_logged_in(self):
        self._post()
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.created_by, self.user)

    def test_post_to_missing_unit_returns_404(self):
        response = self.client.post('/observe/NO-SUCH-UNIT/', {
            'status': Observation.STATUS_HEALTHY,
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        self.assertEqual(response.status_code, 404)


# ── Observe form — POST with photo ────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ObserveFormPostWithPhotoTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-OBS-PHOTO-001', quantity=5)

    def test_post_with_valid_photo_creates_observation_and_photo(self):
        response = self.client.post(
            f'/observe/{self.unit.unit_code}/',
            {
                'status': Observation.STATUS_HEALTHY,
                'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
                'image': create_test_jpeg(),
                'caption': 'Top of tray',
            },
        )
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.photos.count(), 1)
        photo = obs.photos.first()
        self.assertEqual(photo.caption, 'Top of tray')

    def test_post_without_photo_creates_observation_no_photo(self):
        self.client.post(f'/observe/{self.unit.unit_code}/', {
            'status': Observation.STATUS_HEALTHY,
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.photos.count(), 0)


# ── Timeline view ─────────────────────────────────────────────────────────────

class TimelineViewTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-TL-001', crop_name='Cycad', quantity=3)

    def test_timeline_returns_200(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertEqual(response.status_code, 200)

    def test_timeline_contains_unit_code(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, self.unit.unit_code)

    def test_timeline_shows_observations(self):
        make_observation(self.unit, status=Observation.STATUS_SICK, notes='Wilting')
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Sick')
        self.assertContains(response, 'Wilting')

    def test_timeline_missing_unit_returns_404(self):
        response = self.client.get('/observe/MISSING-UNIT/timeline/')
        self.assertEqual(response.status_code, 404)

    def test_timeline_empty_shows_no_observations_message(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'No observations yet')

    def test_timeline_shows_new_observation_link(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, f'/observe/{self.unit.unit_code}/')

    def test_timeline_shows_back_to_dashboard_link(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, '/dashboard/')

    def test_timeline_shows_unit_quantity(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, str(self.unit.quantity))

    def test_timeline_shows_unit_location(self):
        unit = make_unit('TU-TL-LOC-001', location_text='SH1 / Bench Z')
        response = self.client.get(f'/observe/{unit.unit_code}/timeline/')
        self.assertContains(response, 'SH1 / Bench Z')

    def test_timeline_heading_includes_crop_name(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, self.unit.crop_name)


# ── Observe form — oversized photo rejection ──────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OversizedPhotoTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-BIG-PHOTO-001', quantity=5)

    def test_oversized_photo_rejected_and_creates_no_observation(self):
        oversized = create_oversized_file()
        response = self.client.post(
            f'/observe/{self.unit.unit_code}/',
            {
                'status': Observation.STATUS_HEALTHY,
                'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
                'image': oversized,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Observation.objects.filter(tracking_unit=self.unit).exists())

    def test_invalid_photo_shows_error_in_form(self):
        """Any invalid photo upload (oversized, corrupt, wrong type) shows an errorlist."""
        oversized = create_oversized_file()
        response = self.client.post(
            f'/observe/{self.unit.unit_code}/',
            {
                'status': Observation.STATUS_HEALTHY,
                'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
                'image': oversized,
            },
        )
        self.assertContains(response, 'errorlist')


# ── Timeline — photo rendering ────────────────────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TimelinePhotoTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        self.unit = make_unit('TU-TL-PHOTO-001', quantity=5)
        self.obs = make_observation(self.unit, status=Observation.STATUS_HEALTHY)

    def test_timeline_uses_thumbnail_when_available(self):
        ObservationPhoto.objects.create(
            observation=self.obs,
            image=create_test_jpeg(),
        )
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'observation_thumbnails')

    def test_timeline_links_to_original_image(self):
        ObservationPhoto.objects.create(
            observation=self.obs,
            image=create_test_jpeg(),
        )
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'observation_photos')
        self.assertContains(response, 'target="_blank"')

    def test_timeline_falls_back_to_original_when_no_thumbnail(self):
        photo = ObservationPhoto(observation=self.obs, image=create_test_jpeg())
        from django.db.models import Model
        Model.save(photo)
        ObservationPhoto.objects.filter(pk=photo.pk).update(thumbnail='')
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'observation_photos')


# ── Quantity event form — access ──────────────────────────────────────────────

def _qty_url(unit_code):
    return f'/monitoring/units/{unit_code}/quantity-event/'


class QuantityEventAccessTest(TestCase):

    def setUp(self):
        self.unit = make_unit('TU-QA-001', quantity=20)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_403(self):
        make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertEqual(response.status_code, 403)

    def test_manager_gets_200(self):
        make_manager()
        self.client.login(username='mon_manager', password=_PASSWORD)
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertEqual(response.status_code, 200)

    def test_missing_unit_returns_404(self):
        make_manager()
        self.client.login(username='mon_manager', password=_PASSWORD)
        response = self.client.get(_qty_url('NO-SUCH-UNIT'))
        self.assertEqual(response.status_code, 404)


# ── Quantity event form — display ─────────────────────────────────────────────

class QuantityEventFormDisplayTest(TestCase):

    def setUp(self):
        make_manager()
        self.client.login(username='mon_manager', password=_PASSWORD)
        self.unit = make_unit(
            'TU-QD-001',
            crop_name='Display Cassava',
            location_text='SH1 / Bay D',
            quantity=25,
        )

    def test_shows_unit_code(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertContains(response, self.unit.unit_code)

    def test_shows_current_quantity(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertContains(response, '25')

    def test_shows_display_crop(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertContains(response, 'Display Cassava')

    def test_shows_display_location(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertContains(response, 'SH1 / Bay D')

    def test_contains_allowed_event_types(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        for value in ('death', 'loss', 'recount', 'correction'):
            self.assertContains(response, value)

    def test_does_not_expose_forbidden_event_types(self):
        response = self.client.get(_qty_url(self.unit.unit_code))
        for value in ('initial', 'split', 'merge', 'distribution'):
            self.assertNotContains(response, f'value="{value}"')

    def test_prefills_death_suggestion_from_latest_dead_observation(self):
        make_observation(
            self.unit,
            status=Observation.STATUS_DEAD,
            affected_quantity=3,
        )
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertContains(response, 'Suggested quantity change')
        self.assertContains(response, '3 dead plants')
        self.assertEqual(response.context['form'].initial['event_type'], 'death')
        self.assertEqual(response.context['form'].initial['quantity_change'], -3)

    def test_does_not_suggest_when_latest_observation_is_not_dead(self):
        make_observation(
            self.unit,
            status=Observation.STATUS_SICK,
            affected_quantity=3,
        )
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertNotContains(response, 'Suggested quantity change')

    def test_individual_dead_observation_without_affected_quantity_suggests_minus_one(self):
        unit = make_unit(
            'TU-QD-IND-001',
            unit_type=TrackingUnit.UNIT_TYPE_INDIVIDUAL,
            quantity=1,
        )
        make_observation(
            unit,
            status=Observation.STATUS_DEAD,
            affected_quantity=None,
        )
        response = self.client.get(_qty_url(unit.unit_code))
        self.assertContains(response, 'Suggested quantity change')
        self.assertEqual(response.context['form'].initial['quantity_change'], -1)

    def test_does_not_suggest_if_quantity_event_is_newer_than_observation(self):
        make_observation(
            self.unit,
            status=Observation.STATUS_DEAD,
            affected_quantity=2,
        )
        self.client.post(_qty_url(self.unit.unit_code), {
            'event_type': 'death',
            'quantity_change': '-2',
            'reason': 'Applied from latest observation',
        })
        response = self.client.get(_qty_url(self.unit.unit_code))
        self.assertNotContains(response, 'Suggested quantity change')


# ── Quantity event form — POST helpers ────────────────────────────────────────

class QuantityEventPostBase(TestCase):

    def setUp(self):
        self.manager = make_manager()
        self.client.login(username='mon_manager', password=_PASSWORD)
        self.unit = make_unit('TU-QP-001', quantity=20)

    def _post(self, data):
        return self.client.post(_qty_url(self.unit.unit_code), data)

    def _refresh(self):
        self.unit.refresh_from_db()


# ── Death / Loss tests ────────────────────────────────────────────────────────

class QuantityEventDeathLossTest(QuantityEventPostBase):

    def test_manager_submits_death_event_quantity_decreases(self):
        self._post({'event_type': 'death', 'quantity_change': '-3', 'reason': 'Culling'})
        self._refresh()
        self.assertEqual(self.unit.quantity, 17)

    def test_death_event_creates_quantity_event_record(self):
        self._post({'event_type': 'death', 'quantity_change': '-3', 'reason': 'Culling'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.event_type, QuantityEvent.EVENT_TYPE_DEATH)
        self.assertEqual(event.quantity_before, 20)
        self.assertEqual(event.quantity_change, -3)
        self.assertEqual(event.quantity_after, 17)

    def test_death_event_records_reason(self):
        self._post({'event_type': 'death', 'quantity_change': '-5', 'reason': 'Storm damage'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.reason, 'Storm damage')

    def test_positive_death_quantity_change_rejected(self):
        response = self._post({'event_type': 'death', 'quantity_change': '3', 'reason': 'Test'})
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertEqual(self.unit.quantity, 20)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_loss_event_decreases_quantity(self):
        self._post({'event_type': 'loss', 'quantity_change': '-2', 'reason': 'Theft'})
        self._refresh()
        self.assertEqual(self.unit.quantity, 18)

    def test_loss_creates_quantity_event(self):
        self._post({'event_type': 'loss', 'quantity_change': '-2', 'reason': 'Theft'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.event_type, QuantityEvent.EVENT_TYPE_LOSS)

    def test_death_redirects_to_timeline_on_success(self):
        response = self._post({'event_type': 'death', 'quantity_change': '-1', 'reason': 'R'})
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )

    def test_success_message_shows_before_and_after(self):
        response = self._post({'event_type': 'death', 'quantity_change': '-3', 'reason': 'R'})
        # Follow redirect to get messages
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, '20')
        self.assertContains(response, '17')

    def test_death_event_sets_created_by(self):
        self._post({'event_type': 'death', 'quantity_change': '-1', 'reason': 'R'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.created_by, self.manager)


# ── Correction tests ──────────────────────────────────────────────────────────

class QuantityEventCorrectionTest(QuantityEventPostBase):

    def test_correction_can_increase_quantity(self):
        self._post({'event_type': 'correction', 'quantity_change': '5', 'reason': 'Found more'})
        self._refresh()
        self.assertEqual(self.unit.quantity, 25)

    def test_correction_can_decrease_quantity(self):
        self._post({'event_type': 'correction', 'quantity_change': '-4', 'reason': 'Recounted'})
        self._refresh()
        self.assertEqual(self.unit.quantity, 16)

    def test_correction_resulting_in_negative_rejected(self):
        response = self._post({'event_type': 'correction', 'quantity_change': '-25', 'reason': 'R'})
        self.assertEqual(response.status_code, 200)
        self._refresh()
        self.assertEqual(self.unit.quantity, 20)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)


# ── Recount tests ─────────────────────────────────────────────────────────────

class QuantityEventRecountTest(QuantityEventPostBase):

    def test_recount_lower_creates_negative_change(self):
        self._post({'event_type': 'recount', 'physical_quantity': '15', 'reason': 'Manual count'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.quantity_change, -5)
        self.assertEqual(event.quantity_after, 15)

    def test_recount_higher_creates_positive_change(self):
        self._post({'event_type': 'recount', 'physical_quantity': '23', 'reason': 'Manual count'})
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.quantity_change, 3)
        self.assertEqual(event.quantity_after, 23)

    def test_recount_same_as_current_rejected(self):
        response = self._post({'event_type': 'recount', 'physical_quantity': '20', 'reason': 'R'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_recount_negative_physical_quantity_rejected(self):
        response = self._post({'event_type': 'recount', 'physical_quantity': '-5', 'reason': 'R'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_recount_updates_unit_quantity(self):
        self._post({'event_type': 'recount', 'physical_quantity': '18', 'reason': 'R'})
        self._refresh()
        self.assertEqual(self.unit.quantity, 18)

    def test_recount_ignores_submitted_quantity_change_and_uses_physical_quantity(self):
        self._post({
            'event_type': 'recount',
            'quantity_change': '999',
            'physical_quantity': '15',
            'reason': 'Manual count',
        })
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.quantity_change, -5)
        self.assertEqual(event.quantity_after, 15)

    def test_recount_with_invalid_quantity_change_still_succeeds_when_physical_quantity_valid(self):
        response = self._post({
            'event_type': 'recount',
            'quantity_change': 'not-an-integer',
            'physical_quantity': '17',
            'reason': 'Manual count',
        })
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.quantity_change, -3)


# ── Validation tests ──────────────────────────────────────────────────────────

class QuantityEventValidationTest(QuantityEventPostBase):

    def test_reason_required(self):
        response = self._post({'event_type': 'death', 'quantity_change': '-1', 'reason': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_zero_quantity_change_rejected(self):
        response = self._post({'event_type': 'correction', 'quantity_change': '0', 'reason': 'R'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_negative_result_creates_no_event_and_leaves_quantity_unchanged(self):
        unit = make_unit('TU-QV-NEG-001', quantity=3)
        response = self.client.post(_qty_url(unit.unit_code), {
            'event_type': 'death',
            'quantity_change': '-5',
            'reason': 'R',
        })
        self.assertEqual(response.status_code, 200)
        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 3)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=unit).count(), 0)

    def test_observer_post_gets_403(self):
        make_observer()
        self.client.login(username='mon_observer', password=_PASSWORD)
        response = self._post({'event_type': 'death', 'quantity_change': '-1', 'reason': 'R'})
        self.assertEqual(response.status_code, 403)
        self._refresh()
        self.assertEqual(self.unit.quantity, 20)

    def test_missing_quantity_change_for_death_rejected(self):
        response = self._post({'event_type': 'death', 'reason': 'R'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=self.unit).count(), 0)

    def test_death_ignores_submitted_physical_quantity(self):
        response = self._post({
            'event_type': 'death',
            'quantity_change': '-2',
            'physical_quantity': '999',
            'reason': 'R',
        })
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.quantity_change, -2)


# ── Timeline — quantity events display ────────────────────────────────────────

class TimelineQuantityEventsTest(TestCase):

    def setUp(self):
        self.manager = make_manager('tl_qty_manager')
        self.observer = make_observer('tl_qty_observer')
        self.unit = make_unit('TU-TL-QE-001', quantity=20)

    def _create_event(self, quantity_change=-3, reason='Test reason'):
        from monitoring.services import apply_quantity_event
        return apply_quantity_event(
            tracking_unit=self.unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=quantity_change,
            user=self.manager,
            reason=reason,
        )

    def test_timeline_shows_quantity_events(self):
        self._create_event()
        self.client.login(username='tl_qty_observer', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Death')

    def test_timeline_shows_before_change_after_values(self):
        self._create_event(quantity_change=-3)
        self.client.login(username='tl_qty_observer', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        content = response.content.decode()
        self.assertIn('20', content)
        self.assertIn('-3', content)
        self.assertIn('17', content)

    def test_timeline_shows_reason(self):
        self._create_event(reason='Storm damage culling')
        self.client.login(username='tl_qty_observer', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Storm damage culling')

    def test_timeline_manager_sees_record_quantity_change_link(self):
        self.client.login(username='tl_qty_manager', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Record quantity change')
        self.assertContains(response, f'/monitoring/units/{self.unit.unit_code}/quantity-event/')

    def test_timeline_observer_does_not_see_record_quantity_change_link(self):
        self.client.login(username='tl_qty_observer', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertNotContains(response, 'Record quantity change')


# ── Archived unit — observe blocking ─────────────────────────────────────────

class ArchivedUnitObserveTest(TestCase):

    def setUp(self):
        self.user = make_observer('arch_obs_blk')
        self.client.login(username='arch_obs_blk', password=_PASSWORD)
        self.unit = make_unit('TU-ARCH-OBS-001', quantity=5)
        self.unit.is_active = False
        self.unit.archive_reason = 'dead'
        self.unit.save(update_fields=['is_active', 'archive_reason'])

    def test_archived_unit_observe_get_returns_200(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertEqual(response.status_code, 200)

    def test_archived_unit_observe_shows_archived_warning(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, 'archived')

    def test_archived_unit_observe_shows_timeline_link(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, f'/observe/{self.unit.unit_code}/timeline/')

    def test_archived_unit_observe_shows_dashboard_link(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertContains(response, '/dashboard/')

    def test_archived_unit_observe_post_does_not_create_observation(self):
        self.client.post(f'/observe/{self.unit.unit_code}/', {
            'status': Observation.STATUS_HEALTHY,
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        self.assertFalse(Observation.objects.filter(tracking_unit=self.unit).exists())

    def test_active_unit_observe_still_works(self):
        active = make_unit('TU-ARCH-ACTIVE-002', quantity=3)
        response = self.client.post(f'/observe/{active.unit_code}/', {
            'status': Observation.STATUS_HEALTHY,
            'observation_type': Observation.OBSERVATION_TYPE_ROUTINE,
        })
        self.assertRedirects(
            response,
            f'/observe/{active.unit_code}/timeline/',
            fetch_redirect_response=False,
        )
        self.assertTrue(Observation.objects.filter(tracking_unit=active).exists())


# ── Archived unit — timeline ──────────────────────────────────────────────────

class ArchivedUnitTimelineTest(TestCase):

    def setUp(self):
        self.user = make_observer('arch_tl_obs')
        self.client.login(username='arch_tl_obs', password=_PASSWORD)
        self.unit = make_unit('TU-ARCH-TL-001', quantity=2, crop_name='Archive TL Crop')
        make_observation(self.unit, status=Observation.STATUS_DEAD)
        self.unit.is_active = False
        self.unit.archive_reason = 'dead'
        self.unit.save(update_fields=['is_active', 'archive_reason'])

    def test_archived_unit_timeline_returns_200(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertEqual(response.status_code, 200)

    def test_archived_unit_timeline_shows_archived_badge(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Archived')

    def test_archived_unit_timeline_shows_archive_reason(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Dead')

    def test_archived_unit_timeline_shows_observations(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Dead')

    def test_archived_unit_timeline_does_not_show_archive_link(self):
        make_manager('arch_tl_mgr')
        self.client.login(username='arch_tl_mgr', password=_PASSWORD)
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertNotContains(response, 'Archive unit')

    def test_active_unit_timeline_shows_archive_link_for_manager(self):
        make_manager('arch_tl_mgr2')
        self.client.login(username='arch_tl_mgr2', password=_PASSWORD)
        active = make_unit('TU-ARCH-TL-ACTIVE-001', quantity=5)
        response = self.client.get(f'/observe/{active.unit_code}/timeline/')
        self.assertContains(response, 'Archive unit')
        self.assertContains(response, f'/inventory/units/{active.unit_code}/archive/')

    def test_active_unit_timeline_does_not_show_archive_link_for_observer(self):
        active = make_unit('TU-ARCH-TL-OBS-001', quantity=5)
        response = self.client.get(f'/observe/{active.unit_code}/timeline/')
        self.assertNotContains(response, 'Archive unit')


# ── Treatment views ───────────────────────────────────────────────────────────

def make_treatment(unit, **overrides):
    defaults = dict(
        tracking_unit=unit,
        treatment_type=Treatment.TYPE_WATERED,
        reason='Test treatment reason',
    )
    defaults.update(overrides)
    return Treatment.objects.create(**defaults)


class TreatmentAccessTest(TestCase):

    def setUp(self):
        self.unit = make_unit('TU-TX-ACCESS-001', quantity=5)

    def test_anonymous_create_treatment_redirects_to_login(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_create_treatment_gets_403(self):
        observer = make_observer(username='tx_obs_access')
        self.client.login(username='tx_obs_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_access_create_treatment_page(self):
        manager = make_manager(username='tx_mgr_access')
        self.client.login(username='tx_mgr_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertEqual(response.status_code, 200)

    def test_archived_unit_treatment_create_redirects_with_message(self):
        archived = make_unit('TU-TX-ARCH-001', quantity=5, is_active=False)
        manager = make_manager(username='tx_mgr_arch')
        self.client.login(username='tx_mgr_arch', password=_PASSWORD)
        response = self.client.post(
            f'/monitoring/units/{archived.unit_code}/treatments/new/',
            {'treatment_type': Treatment.TYPE_WATERED, 'reason': 'Should not work'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Treatment.objects.count(), 0)


class TreatmentCreatePageTest(TestCase):

    def setUp(self):
        self.manager = make_manager(username='tx_mgr_page')
        self.client.login(username='tx_mgr_page', password=_PASSWORD)
        self.unit = make_unit('TU-TX-PAGE-001', crop_name='Baobab', location_text='Bay 5', quantity=8)

    def test_treatment_page_shows_unit_code(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertContains(response, self.unit.unit_code)

    def test_treatment_page_shows_crop(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertContains(response, 'Baobab')

    def test_treatment_page_shows_location(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/treatments/new/')
        self.assertContains(response, 'Bay 5')

    def test_manager_can_create_treatment(self):
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_FUNGICIDE,
                'reason': 'Powdery mildew spotted',
                'outcome': Treatment.OUTCOME_PENDING,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Treatment.objects.count(), 1)

    def test_created_by_is_set(self):
        self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_FUNGICIDE,
                'reason': 'Mildew',
                'outcome': Treatment.OUTCOME_PENDING,
            },
        )
        tx = Treatment.objects.get()
        self.assertEqual(tx.created_by, self.manager)

    def test_valid_treatment_redirects_to_timeline(self):
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_WATERED,
                'reason': 'Dry soil',
                'outcome': Treatment.OUTCOME_PENDING,
            },
        )
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )

    def test_success_message_appears(self):
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_WATERED,
                'reason': 'Dry',
                'outcome': Treatment.OUTCOME_PENDING,
            },
            follow=True,
        )
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Treatment recorded' in m for m in messages))

    def test_missing_reason_is_rejected(self):
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_WATERED,
                'reason': '',
                'outcome': Treatment.OUTCOME_PENDING,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Treatment.objects.count(), 0)

    def test_past_follow_up_date_is_rejected(self):
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_WATERED,
                'reason': 'Test',
                'outcome': Treatment.OUTCOME_PENDING,
                'follow_up_date': yesterday,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Treatment.objects.count(), 0)

    def test_treatment_for_archived_unit_is_not_created(self):
        archived = make_unit('TU-TX-ARCH-POST-001', quantity=5, is_active=False)
        response = self.client.post(
            f'/monitoring/units/{archived.unit_code}/treatments/new/',
            {
                'treatment_type': Treatment.TYPE_WATERED,
                'reason': 'Should not be created',
                'outcome': Treatment.OUTCOME_PENDING,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Treatment.objects.count(), 0)


class TreatmentTimelineTest(TestCase):

    def setUp(self):
        self.manager = make_manager(username='tx_mgr_tl')
        self.observer = make_observer(username='tx_obs_tl')
        self.unit = make_unit('TU-TX-TL-001', quantity=5)
        self.treatment = make_treatment(
            self.unit,
            treatment_type=Treatment.TYPE_FUNGICIDE,
            reason='Leaf spot infection',
            product_used='Mancozeb',
            dose_rate='2 g/L',
            outcome=Treatment.OUTCOME_PENDING,
        )

    def _get_timeline(self, user):
        self.client.login(username=user.username, password=_PASSWORD)
        return self.client.get(f'/observe/{self.unit.unit_code}/timeline/')

    def test_timeline_shows_treatment_type(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Fungicide')

    def test_timeline_shows_product_used(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Mancozeb')

    def test_timeline_shows_dose_rate(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, '2 g/L')

    def test_timeline_shows_reason(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Leaf spot infection')

    def test_timeline_shows_outcome(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Pending')

    def test_manager_sees_record_treatment_link_for_active_unit(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Record treatment')

    def test_observer_does_not_see_record_treatment_link(self):
        response = self._get_timeline(self.observer)
        self.assertNotContains(response, 'Record treatment')

    def test_archived_unit_does_not_show_record_treatment_link(self):
        self.unit.is_active = False
        self.unit.save()
        response = self._get_timeline(self.manager)
        self.assertNotContains(response, 'Record treatment')


class TreatmentOutcomeUpdateTest(TestCase):

    def setUp(self):
        self.manager = make_manager(username='tx_mgr_outcome')
        self.observer = make_observer(username='tx_obs_outcome')
        self.unit = make_unit('TU-TX-OUT-001', quantity=5)
        self.treatment = make_treatment(self.unit)

    def test_anonymous_outcome_page_redirects(self):
        response = self.client.get(f'/monitoring/treatments/{self.treatment.pk}/outcome/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_outcome_page_gets_403(self):
        self.client.login(username='tx_obs_outcome', password=_PASSWORD)
        response = self.client.get(f'/monitoring/treatments/{self.treatment.pk}/outcome/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_access_outcome_page(self):
        self.client.login(username='tx_mgr_outcome', password=_PASSWORD)
        response = self.client.get(f'/monitoring/treatments/{self.treatment.pk}/outcome/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_update_outcome_to_improved(self):
        self.client.login(username='tx_mgr_outcome', password=_PASSWORD)
        self.client.post(
            f'/monitoring/treatments/{self.treatment.pk}/outcome/',
            {'outcome': Treatment.OUTCOME_IMPROVED, 'notes': 'Plant has recovered'},
        )
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.outcome, Treatment.OUTCOME_IMPROVED)

    def test_updated_outcome_appears_on_timeline(self):
        self.client.login(username='tx_mgr_outcome', password=_PASSWORD)
        self.client.post(
            f'/monitoring/treatments/{self.treatment.pk}/outcome/',
            {'outcome': Treatment.OUTCOME_RESOLVED, 'notes': ''},
        )
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertContains(response, 'Resolved')
