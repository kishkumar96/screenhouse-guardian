import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

import datetime

from inventory.models import Bench, Position, ScreenHouse, Site, TrackingUnit
from monitoring.models import (
    EnvironmentalLog, MAX_OBSERVATION_IMAGE_SIZE_BYTES, Observation, ObservationPhoto, QuantityEvent, Treatment,
)

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


class TimelineMovementHistoryTest(TestCase):

    def setUp(self):
        from inventory.services import record_movement
        self.manager = make_manager(username='mv_mgr_tl')
        self.observer = make_observer(username='mv_obs_tl')
        self.unit = make_unit('TU-MOVE-TL-001', quantity=5, location_text='Bay A')
        record_movement(
            tracking_unit=self.unit,
            to_location_text='Bay B',
            user=self.manager,
            reason='Better airflow',
        )

    def _get_timeline(self, user):
        self.client.login(username=user.username, password=_PASSWORD)
        return self.client.get(f'/observe/{self.unit.unit_code}/timeline/')

    def test_timeline_shows_movement_history_heading(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Movement History')

    def test_timeline_shows_from_and_to_locations(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Bay A')
        self.assertContains(response, 'Bay B')

    def test_timeline_shows_move_reason(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Better airflow')

    def test_manager_sees_move_unit_link_for_active_unit(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Move unit')

    def test_observer_does_not_see_move_unit_link(self):
        response = self._get_timeline(self.observer)
        self.assertNotContains(response, 'Move unit')

    def test_archived_unit_does_not_show_move_unit_link(self):
        self.unit.is_active = False
        self.unit.save()
        response = self._get_timeline(self.manager)
        self.assertNotContains(response, 'Move unit')


# ── Distribution events ───────────────────────────────────────────────────────

class DistributionAccessTest(TestCase):

    def setUp(self):
        self.observer = make_observer(username='dist_obs_access')
        self.manager = make_manager(username='dist_mgr_access')
        self.unit = make_unit('TU-DIST-ACC-001', quantity=10)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/distribute/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_403(self):
        self.client.login(username='dist_obs_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/distribute/')
        self.assertEqual(response.status_code, 403)

    def test_manager_gets_200(self):
        self.client.login(username='dist_mgr_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/distribute/')
        self.assertEqual(response.status_code, 200)

    def test_archived_unit_redirects(self):
        archived = make_unit('TU-DIST-ARCH-001', quantity=5, is_active=False)
        self.client.login(username='dist_mgr_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{archived.unit_code}/distribute/')
        self.assertEqual(response.status_code, 302)


class DistributionPostTest(TestCase):

    def setUp(self):
        make_manager(username='dist_mgr_post')
        self.client.login(username='dist_mgr_post', password=_PASSWORD)
        self.unit = make_unit('TU-DIST-POST-001', quantity=20)

    def _post(self, **overrides):
        data = {
            'quantity': '5',
            'recipient_name': 'Botanic Garden',
            'recipient_organisation': '',
            'purpose': '',
            'notes': '',
        }
        data.update(overrides)
        return self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/distribute/', data,
        )

    def test_valid_post_reduces_quantity(self):
        self._post()
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 15)

    def test_valid_post_redirects_to_timeline(self):
        response = self._post()
        self.assertRedirects(response, f'/observe/{self.unit.unit_code}/timeline/')

    def test_quantity_exceeding_available_is_rejected(self):
        response = self._post(quantity='999')
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 20)

    def test_missing_recipient_name_is_rejected(self):
        response = self._post(recipient_name='')
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 20)

    def test_observer_cannot_post(self):
        make_observer(username='dist_post_obs')
        self.client.login(username='dist_post_obs', password=_PASSWORD)
        response = self._post()
        self.assertEqual(response.status_code, 403)


class TimelineDistributionHistoryTest(TestCase):

    def setUp(self):
        from monitoring.services import record_distribution
        self.manager = make_manager(username='dist_mgr_tl')
        self.observer = make_observer(username='dist_obs_tl')
        self.unit = make_unit('TU-DIST-TL-001', quantity=20)
        record_distribution(
            tracking_unit=self.unit, quantity=5, recipient_name='Botanic Garden',
            recipient_organisation='National Trust', purpose='Research exchange',
            user=self.manager,
        )

    def _get_timeline(self, user):
        self.client.login(username=user.username, password=_PASSWORD)
        return self.client.get(f'/observe/{self.unit.unit_code}/timeline/')

    def test_timeline_shows_distribution_heading(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Distribution History')

    def test_timeline_shows_recipient(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Botanic Garden')
        self.assertContains(response, 'National Trust')

    def test_timeline_shows_purpose(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Research exchange')

    def test_manager_sees_record_distribution_link(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Record distribution')

    def test_observer_does_not_see_record_distribution_link(self):
        response = self._get_timeline(self.observer)
        self.assertNotContains(response, 'Record distribution')


# ── Propagation events ────────────────────────────────────────────────────────

class PropagationAccessTest(TestCase):

    def setUp(self):
        self.observer = make_observer(username='prop_obs_access')
        self.manager = make_manager(username='prop_mgr_access')
        self.unit = make_unit('TU-PROP-ACC-001', quantity=10)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/propagate/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_403(self):
        self.client.login(username='prop_obs_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/propagate/')
        self.assertEqual(response.status_code, 403)

    def test_manager_gets_200(self):
        self.client.login(username='prop_mgr_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{self.unit.unit_code}/propagate/')
        self.assertEqual(response.status_code, 200)

    def test_archived_unit_redirects(self):
        archived = make_unit('TU-PROP-ARCH-001', quantity=5, is_active=False)
        self.client.login(username='prop_mgr_access', password=_PASSWORD)
        response = self.client.get(f'/monitoring/units/{archived.unit_code}/propagate/')
        self.assertEqual(response.status_code, 302)


class PropagationPostTest(TestCase):

    def setUp(self):
        make_manager(username='prop_mgr_post')
        self.client.login(username='prop_mgr_post', password=_PASSWORD)
        self.unit = make_unit('TU-PROP-POST-001', quantity=20)

    def test_valid_post_creates_event(self):
        from monitoring.models import PropagationEvent
        self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/propagate/',
            {'method': PropagationEvent.METHOD_CUTTING, 'quantity_taken': '', 'resulting_units': []},
        )
        self.assertTrue(PropagationEvent.objects.filter(parent_unit=self.unit).exists())

    def test_valid_post_redirects_to_timeline(self):
        from monitoring.models import PropagationEvent
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/propagate/',
            {'method': PropagationEvent.METHOD_CUTTING, 'quantity_taken': '', 'resulting_units': []},
        )
        self.assertRedirects(response, f'/observe/{self.unit.unit_code}/timeline/')

    def test_quantity_taken_reduces_parent(self):
        from monitoring.models import PropagationEvent
        self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/propagate/',
            {'method': PropagationEvent.METHOD_CUTTING, 'quantity_taken': '4', 'resulting_units': []},
        )
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 16)

    def test_quantity_taken_exceeding_available_is_rejected(self):
        from monitoring.models import PropagationEvent
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/propagate/',
            {'method': PropagationEvent.METHOD_CUTTING, 'quantity_taken': '999', 'resulting_units': []},
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 20)

    def test_observer_cannot_post(self):
        from monitoring.models import PropagationEvent
        make_observer(username='prop_post_obs')
        self.client.login(username='prop_post_obs', password=_PASSWORD)
        response = self.client.post(
            f'/monitoring/units/{self.unit.unit_code}/propagate/',
            {'method': PropagationEvent.METHOD_CUTTING, 'quantity_taken': '', 'resulting_units': []},
        )
        self.assertEqual(response.status_code, 403)


class TimelinePropagationHistoryTest(TestCase):

    def setUp(self):
        from monitoring.models import PropagationEvent
        from monitoring.services import record_propagation
        self.manager = make_manager(username='prop_mgr_tl')
        self.observer = make_observer(username='prop_obs_tl')
        self.unit = make_unit('TU-PROP-TL-001', quantity=20)
        self.child = make_unit('TU-PROP-TL-001-C1', quantity=1)
        record_propagation(
            parent_unit=self.unit, method=PropagationEvent.METHOD_CUTTING,
            quantity_taken=3, notes='Rooted cuttings', user=self.manager,
            resulting_units=[self.child],
        )

    def _get_timeline(self, user):
        self.client.login(username=user.username, password=_PASSWORD)
        return self.client.get(f'/observe/{self.unit.unit_code}/timeline/')

    def test_timeline_shows_propagation_heading(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Propagation History')

    def test_timeline_shows_method(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Cutting')

    def test_timeline_shows_resulting_unit(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, self.child.unit_code)

    def test_timeline_shows_notes(self):
        response = self._get_timeline(self.observer)
        self.assertContains(response, 'Rooted cuttings')

    def test_manager_sees_record_propagation_link(self):
        response = self._get_timeline(self.manager)
        self.assertContains(response, 'Record propagation')

    def test_observer_does_not_see_record_propagation_link(self):
        response = self._get_timeline(self.observer)
        self.assertNotContains(response, 'Record propagation')


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


# ── Daily round view tests ────────────────────────────────────────────────────

import datetime as dt

from monitoring.models import DailyRound, DailyRoundItem


def make_round(name='Test round', date=None, **kwargs):
    if date is None:
        date = dt.date.today()
    return DailyRound.objects.create(name=name, date=date, **kwargs)


def make_round_item(daily_round, unit, **kwargs):
    return DailyRoundItem.objects.create(daily_round=daily_round, tracking_unit=unit, **kwargs)


class RoundListAccessTest(TestCase):

    def test_anonymous_redirects_to_login(self):
        response = self.client.get('/monitoring/rounds/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_can_access_round_list(self):
        obs = make_observer(username='rd_obs_list')
        self.client.login(username='rd_obs_list', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_round_list(self):
        mgr = make_manager(username='rd_mgr_list')
        self.client.login(username='rd_mgr_list', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/')
        self.assertEqual(response.status_code, 200)


class RoundCreateAccessTest(TestCase):

    def test_observer_cannot_access_round_create_page(self):
        obs = make_observer(username='rd_obs_create')
        self.client.login(username='rd_obs_create', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/new/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_access_round_create_page(self):
        mgr = make_manager(username='rd_mgr_create')
        self.client.login(username='rd_mgr_create', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/new/')
        self.assertEqual(response.status_code, 200)

    def test_round_create_form_shows_generation_modes(self):
        mgr = make_manager(username='rd_mgr_modes')
        self.client.login(username='rd_mgr_modes', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/new/')
        self.assertContains(response, 'all_active')

    def test_manager_can_create_all_active_round(self):
        mgr = make_manager(username='rd_mgr_allact')
        self.client.login(username='rd_mgr_allact', password=_PASSWORD)
        make_unit('TU-RD-ALLACT-001')
        response = self.client.post('/monitoring/rounds/new/', {
            'name': 'Morning round',
            'date': dt.date.today().isoformat(),
            'generation_mode': 'all_active',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DailyRound.objects.count(), 1)


class RoundDetailAccessTest(TestCase):

    def setUp(self):
        self.dr = make_round()

    def test_anonymous_round_detail_redirects_to_login(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_can_access_round_detail(self):
        obs = make_observer(username='rd_obs_detail')
        self.client.login(username='rd_obs_detail', password=_PASSWORD)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertEqual(response.status_code, 200)


class RoundDetailContentTest(TestCase):

    def setUp(self):
        self.mgr = make_manager(username='rd_mgr_det')
        self.client.login(username='rd_mgr_det', password=_PASSWORD)
        self.unit = make_unit('TU-RD-DET-001', crop_name='Baobab', location_text='Bay 2', quantity=5)
        self.dr = make_round('Morning check')
        self.item = make_round_item(self.dr, self.unit)

    def test_round_detail_shows_unit_code(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertContains(response, self.unit.unit_code)

    def test_round_detail_shows_progress_count(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        # total = 1, done = 0
        self.assertContains(response, '0')
        self.assertContains(response, '1')

    def test_round_detail_shows_observe_link_with_round_item_param(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertContains(response, f'round_item={self.item.pk}')


class ObserveFromRoundTest(TestCase):

    def setUp(self):
        self.observer = make_observer(username='rd_obs_observe')
        self.client.login(username='rd_obs_observe', password=_PASSWORD)
        self.unit = make_unit('TU-RD-OBS-001', quantity=5)
        self.dr = make_round()
        self.item = make_round_item(self.dr, self.unit)

    def test_invalid_round_item_for_different_unit_returns_404(self):
        other_unit = make_unit('TU-RD-OTHER-001', quantity=5)
        other_item = make_round_item(self.dr, other_unit)
        response = self.client.get(
            f'/observe/{self.unit.unit_code}/?round_item={other_item.pk}'
        )
        self.assertEqual(response.status_code, 404)

    def test_observation_from_round_marks_item_completed(self):
        self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.item.refresh_from_db()
        self.assertTrue(self.item.completed)

    def test_observation_from_round_links_observation_to_item(self):
        self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.observation_id)

    def test_observation_from_round_sets_completed_at(self):
        self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.completed_at)

    def test_observation_from_round_redirects_to_round_detail(self):
        response = self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.assertRedirects(
            response,
            f'/monitoring/rounds/{self.dr.pk}/',
            fetch_redirect_response=False,
        )

    def test_completing_first_item_updates_round_to_in_progress(self):
        second_unit = make_unit('TU-RD-OBS-002', quantity=5)
        make_round_item(self.dr, second_unit)
        self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_IN_PROGRESS)

    def test_completing_all_items_updates_round_to_completed(self):
        self.client.post(
            f'/observe/{self.unit.unit_code}/?round_item={self.item.pk}',
            {
                'status': 'healthy',
                'observation_type': 'routine',
                'round_item': str(self.item.pk),
            },
        )
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_COMPLETED)

    def test_normal_observation_without_round_item_still_works(self):
        response = self.client.post(
            f'/observe/{self.unit.unit_code}/',
            {
                'status': 'healthy',
                'observation_type': 'routine',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            f'/observe/{self.unit.unit_code}/timeline/',
            fetch_redirect_response=False,
        )

    def test_round_list_returns_200(self):
        response = self.client.get('/monitoring/rounds/')
        self.assertEqual(response.status_code, 200)


# ── Fix 1: N+1 verification — round_detail uses annotations ──────────────────

class RoundDetailAnnotationTest(TestCase):

    def setUp(self):
        self.mgr = make_manager(username='rd_ann_mgr')
        self.client.login(username='rd_ann_mgr', password=_PASSWORD)
        self.unit = make_unit('TU-ANN-001', quantity=5)
        self.dr = make_round('Annotation round')
        make_round_item(self.dr, self.unit)
        make_observation(self.unit, status='sick')

    def test_round_detail_shows_status_from_annotation(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sick')

    def test_round_detail_shows_not_checked_when_no_obs(self):
        unit2 = make_unit('TU-ANN-002', quantity=5)
        make_round_item(self.dr, unit2)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertContains(response, 'Not checked')


# ── Fix 2: round editing views ────────────────────────────────────────────────

class RoundEditAccessTest(TestCase):

    def setUp(self):
        self.dr = make_round()

    def test_anonymous_edit_redirects_to_login(self):
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/edit/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_403_on_edit(self):
        obs = make_observer(username='rd_edit_obs')
        self.client.login(username='rd_edit_obs', password=_PASSWORD)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/edit/')
        self.assertEqual(response.status_code, 403)

    def test_manager_can_access_edit_page(self):
        mgr = make_manager(username='rd_edit_mgr')
        self.client.login(username='rd_edit_mgr', password=_PASSWORD)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/edit/')
        self.assertEqual(response.status_code, 200)

    def test_edit_page_shows_current_round_name(self):
        mgr = make_manager(username='rd_edit_mgr2')
        self.client.login(username='rd_edit_mgr2', password=_PASSWORD)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/edit/')
        self.assertContains(response, self.dr.name)

    def test_manager_can_update_round_status(self):
        mgr = make_manager(username='rd_edit_mgr3')
        self.client.login(username='rd_edit_mgr3', password=_PASSWORD)
        self.client.post(f'/monitoring/rounds/{self.dr.pk}/edit/', {
            'name': self.dr.name,
            'date': self.dr.date.isoformat(),
            'status': DailyRound.STATUS_CANCELLED,
        })
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_CANCELLED)

    def test_edit_redirects_to_round_detail_on_success(self):
        mgr = make_manager(username='rd_edit_mgr4')
        self.client.login(username='rd_edit_mgr4', password=_PASSWORD)
        response = self.client.post(f'/monitoring/rounds/{self.dr.pk}/edit/', {
            'name': 'Updated name',
            'date': self.dr.date.isoformat(),
            'status': DailyRound.STATUS_PLANNED,
        })
        self.assertRedirects(
            response,
            f'/monitoring/rounds/{self.dr.pk}/',
            fetch_redirect_response=False,
        )

    def test_manager_sees_edit_link_on_round_list(self):
        mgr = make_manager(username='rd_edit_list_mgr')
        self.client.login(username='rd_edit_list_mgr', password=_PASSWORD)
        response = self.client.get('/monitoring/rounds/')
        self.assertContains(response, f'/monitoring/rounds/{self.dr.pk}/edit/')

    def test_manager_sees_edit_link_on_round_detail(self):
        mgr = make_manager(username='rd_edit_det_mgr')
        self.client.login(username='rd_edit_det_mgr', password=_PASSWORD)
        response = self.client.get(f'/monitoring/rounds/{self.dr.pk}/')
        self.assertContains(response, f'/monitoring/rounds/{self.dr.pk}/edit/')


# ── Fix 3: missed automation from views ───────────────────────────────────────

class RoundListMissedAutomationTest(TestCase):

    def setUp(self):
        obs = make_observer(username='rd_missed_obs')
        self.client.login(username='rd_missed_obs', password=_PASSWORD)

    def test_round_list_auto_marks_overdue_round_missed(self):
        yesterday = dt.date.today() - dt.timedelta(days=1)
        dr = DailyRound.objects.create(name='Old', date=yesterday, status=DailyRound.STATUS_PLANNED)
        self.client.get('/monitoring/rounds/')
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_MISSED)

    def test_round_detail_auto_marks_overdue_round_missed(self):
        yesterday = dt.date.today() - dt.timedelta(days=1)
        dr = DailyRound.objects.create(name='Old det', date=yesterday, status=DailyRound.STATUS_PLANNED)
        self.client.get(f'/monitoring/rounds/{dr.pk}/')
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_MISSED)

    def test_todays_round_stays_planned_after_list_view(self):
        dr = DailyRound.objects.create(name='Today', date=dt.date.today())
        self.client.get('/monitoring/rounds/')
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_PLANNED)


# ── Follow-up list view tests ─────────────────────────────────────────────────

import datetime as _dt
from monitoring.models import Treatment


def _make_treatment_with_followup(unit, follow_up_date=None, outcome=Treatment.OUTCOME_PENDING,
                                  treatment_type=Treatment.TYPE_FUNGICIDE, **kwargs):
    if follow_up_date is None:
        follow_up_date = _dt.date.today()
    return Treatment.objects.create(
        tracking_unit=unit,
        treatment_type=treatment_type,
        reason='Test treatment',
        follow_up_date=follow_up_date,
        outcome=outcome,
        **kwargs,
    )


def _make_treatment_no_followup(unit, **kwargs):
    return Treatment.objects.create(
        tracking_unit=unit,
        treatment_type=Treatment.TYPE_WATERED,
        reason='No follow-up',
        **kwargs,
    )


class FollowUpListAccessTest(TestCase):

    def test_anonymous_redirects_to_login(self):
        response = self.client.get('/monitoring/follow-ups/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_can_access(self):
        obs = make_observer(username='fu_obs_access')
        self.client.login(username='fu_obs_access', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access(self):
        mgr = make_manager(username='fu_mgr_access')
        self.client.login(username='fu_mgr_access', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertEqual(response.status_code, 200)


class FollowUpListFilterTest(TestCase):

    def setUp(self):
        self.obs_user = make_observer(username='fu_obs_filter')
        self.client.login(username='fu_obs_filter', password=_PASSWORD)
        self.unit = make_unit('TU-FU-FILTER-001', quantity=5)

        today = _dt.date.today()
        self.past = today - _dt.timedelta(days=3)
        self.future = today + _dt.timedelta(days=7)

        self.overdue_tx = _make_treatment_with_followup(
            self.unit, follow_up_date=self.past, outcome=Treatment.OUTCOME_PENDING
        )
        self.due_today_tx = _make_treatment_with_followup(
            make_unit('TU-FU-FILTER-002', quantity=5),
            follow_up_date=today, outcome=Treatment.OUTCOME_PENDING
        )
        self.future_tx = _make_treatment_with_followup(
            make_unit('TU-FU-FILTER-003', quantity=5),
            follow_up_date=self.future, outcome=Treatment.OUTCOME_PENDING
        )
        self.resolved_tx = _make_treatment_with_followup(
            make_unit('TU-FU-FILTER-004', quantity=5),
            follow_up_date=self.past, outcome=Treatment.OUTCOME_RESOLVED
        )
        self.no_followup_tx = _make_treatment_no_followup(
            make_unit('TU-FU-FILTER-005', quantity=5)
        )

    def test_only_treatments_with_follow_up_date_shown(self):
        response = self.client.get('/monitoring/follow-ups/?status=all')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertNotIn(self.no_followup_tx.pk, treatment_pks)

    def test_default_filter_shows_pending(self):
        response = self.client.get('/monitoring/follow-ups/')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(self.overdue_tx.pk, treatment_pks)
        self.assertIn(self.due_today_tx.pk, treatment_pks)
        self.assertIn(self.future_tx.pk, treatment_pks)

    def test_default_filter_hides_resolved(self):
        response = self.client.get('/monitoring/follow-ups/')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertNotIn(self.resolved_tx.pk, treatment_pks)

    def test_status_all_shows_resolved(self):
        response = self.client.get('/monitoring/follow-ups/?status=all')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(self.resolved_tx.pk, treatment_pks)

    def test_status_due_today_shows_only_due_today(self):
        response = self.client.get('/monitoring/follow-ups/?status=due_today')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(self.due_today_tx.pk, treatment_pks)
        self.assertNotIn(self.overdue_tx.pk, treatment_pks)
        self.assertNotIn(self.future_tx.pk, treatment_pks)

    def test_status_overdue_shows_only_overdue_pending(self):
        response = self.client.get('/monitoring/follow-ups/?status=overdue')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(self.overdue_tx.pk, treatment_pks)
        self.assertNotIn(self.due_today_tx.pk, treatment_pks)
        self.assertNotIn(self.future_tx.pk, treatment_pks)
        self.assertNotIn(self.resolved_tx.pk, treatment_pks)

    def test_status_completed_shows_improved_no_change_worsened_resolved(self):
        unit2 = make_unit('TU-FU-COMP-001', quantity=5)
        improved_tx = _make_treatment_with_followup(unit2, outcome=Treatment.OUTCOME_IMPROVED)
        response = self.client.get('/monitoring/follow-ups/?status=completed')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(self.resolved_tx.pk, treatment_pks)
        self.assertIn(improved_tx.pk, treatment_pks)
        self.assertNotIn(self.overdue_tx.pk, treatment_pks)

    def test_treatment_type_filter(self):
        unit2 = make_unit('TU-FU-TYPE-001', quantity=5)
        watered_tx = _make_treatment_with_followup(
            unit2, treatment_type=Treatment.TYPE_WATERED
        )
        response = self.client.get(
            '/monitoring/follow-ups/?status=pending&treatment_type=watered'
        )
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(watered_tx.pk, treatment_pks)
        self.assertNotIn(self.overdue_tx.pk, treatment_pks)

    def test_location_filter(self):
        unit_bay9 = make_unit('TU-FU-LOC-001', quantity=5, location_text='Bay 9')
        tx_bay9 = _make_treatment_with_followup(unit_bay9)
        response = self.client.get('/monitoring/follow-ups/?status=pending&location=Bay+9')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(tx_bay9.pk, treatment_pks)
        # Other units not in Bay 9 should be excluded
        for pk in treatment_pks:
            tx = Treatment.objects.get(pk=pk)
            self.assertIn('Bay 9', tx.tracking_unit.location_text)

    def test_crop_filter(self):
        from inventory.models import Crop
        crop_obj = Crop.objects.create(name='Baobab', scientific_name='Adansonia', created_by=None)
        unit_crop = make_unit('TU-FU-CROP-001', quantity=5, crop_name='Baobab')
        unit_crop.crop = crop_obj
        unit_crop.save(update_fields=['crop'])
        tx_baobab = _make_treatment_with_followup(unit_crop)
        response = self.client.get('/monitoring/follow-ups/?status=pending&crop=baobab')
        treatment_pks = {tx.pk for tx in response.context['treatments']}
        self.assertIn(tx_baobab.pk, treatment_pks)


class FollowUpSummaryCountsTest(TestCase):

    def setUp(self):
        self.obs_user = make_observer(username='fu_obs_counts')
        self.client.login(username='fu_obs_counts', password=_PASSWORD)
        self.unit = make_unit('TU-FU-COUNTS-001', quantity=5)
        today = _dt.date.today()
        past = today - _dt.timedelta(days=2)
        future = today + _dt.timedelta(days=5)

        _make_treatment_with_followup(
            make_unit('TU-FU-C1', quantity=5), follow_up_date=past
        )  # overdue pending
        _make_treatment_with_followup(
            make_unit('TU-FU-C2', quantity=5), follow_up_date=today
        )  # due today pending
        _make_treatment_with_followup(
            make_unit('TU-FU-C3', quantity=5), follow_up_date=future
        )  # future pending
        _make_treatment_with_followup(
            make_unit('TU-FU-C4', quantity=5),
            follow_up_date=past, outcome=Treatment.OUTCOME_RESOLVED
        )  # completed

    def test_summary_counts_in_context(self):
        response = self.client.get('/monitoring/follow-ups/')
        counts = response.context['counts']
        self.assertEqual(counts['pending'], 3)
        self.assertEqual(counts['due_today'], 1)
        self.assertEqual(counts['overdue'], 1)
        self.assertEqual(counts['completed'], 1)


class FollowUpListContentTest(TestCase):

    def setUp(self):
        self.mgr = make_manager(username='fu_mgr_content')
        self.obs = make_observer(username='fu_obs_content')
        self.unit = make_unit('TU-FU-CONTENT-001', crop_name='Cassava',
                               location_text='Bay 2', quantity=10)
        today = _dt.date.today()
        self.tx = _make_treatment_with_followup(
            self.unit,
            follow_up_date=today + _dt.timedelta(days=3),
            treatment_type=Treatment.TYPE_FUNGICIDE,
        )

    def test_row_shows_unit_code(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, self.unit.unit_code)

    def test_row_shows_crop(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, 'Cassava')

    def test_row_shows_location(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, 'Bay 2')

    def test_row_shows_treatment_type(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, 'Fungicide')

    def test_row_shows_follow_up_date(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        from django.utils.formats import date_format
        self.assertContains(response, self.tx.follow_up_date.strftime('%-d %b %Y').lstrip('0'))

    def test_row_shows_outcome_badge(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, 'Pending')

    def test_observer_sees_timeline_link(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, f'/observe/{self.unit.unit_code}/timeline/')

    def test_observer_sees_observe_link(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, f'/observe/{self.unit.unit_code}/')

    def test_observer_does_not_see_update_outcome_link(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertNotContains(response, f'/monitoring/treatments/{self.tx.pk}/outcome/')

    def test_manager_sees_update_outcome_link(self):
        self.client.login(username='fu_mgr_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/')
        self.assertContains(response, f'/monitoring/treatments/{self.tx.pk}/outcome/')

    def test_empty_state_when_no_follow_ups_match(self):
        self.client.login(username='fu_obs_content', password=_PASSWORD)
        response = self.client.get('/monitoring/follow-ups/?status=due_today&treatment_type=insecticide')
        self.assertContains(response, 'No follow-ups match')


# ── Weekly report ─────────────────────────────────────────────────────────────

class WeeklyReportAccessTest(TestCase):

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_forbidden(self):
        make_observer(username='wr_observer_access')
        self.client.login(username='wr_observer_access', password=_PASSWORD)
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertEqual(response.status_code, 403)

    def test_manager_allowed(self):
        make_manager(username='wr_manager_access')
        self.client.login(username='wr_manager_access', password=_PASSWORD)
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertEqual(response.status_code, 200)


class WeeklyReportContentTest(TestCase):

    def setUp(self):
        make_manager(username='wr_mgr_content')
        self.client.login(username='wr_mgr_content', password=_PASSWORD)
        self.unit = make_unit('TU-WR-CONTENT-001', crop_name='Cassava')

    def test_shows_date_range_heading(self):
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Weekly Report')

    def test_shows_observation_logged_this_week(self):
        make_observation(self.unit, status=Observation.STATUS_SICK)
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertContains(response, 'Sick')

    def test_shows_treatment_applied_this_week(self):
        _make_treatment_with_followup(self.unit, treatment_type=Treatment.TYPE_FUNGICIDE)
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertContains(response, 'Fungicide')

    def test_current_week_hides_next_week_link(self):
        response = self.client.get('/monitoring/reports/weekly/')
        self.assertContains(response, 'Current week')
        self.assertNotContains(response, 'Next week')

    def test_previous_week_link_navigates_correctly(self):
        response = self.client.get('/monitoring/reports/weekly/')
        prev_end = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
        self.assertContains(response, f'?end_date={prev_end}')

    def test_past_week_shows_next_week_link(self):
        old_end = (_dt.date.today() - _dt.timedelta(days=14)).isoformat()
        response = self.client.get(f'/monitoring/reports/weekly/?end_date={old_end}')
        self.assertContains(response, 'Next week')

    def test_invalid_end_date_falls_back_to_current_week(self):
        response = self.client.get('/monitoring/reports/weekly/?end_date=not-a-date')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current week')


# ── Inventory reconciliation ─────────────────────────────────────────────────

class ReconcileInventoryAccessTest(TestCase):

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get('/monitoring/reconcile/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_forbidden(self):
        make_observer(username='rc_observer_access')
        self.client.login(username='rc_observer_access', password=_PASSWORD)
        response = self.client.get('/monitoring/reconcile/')
        self.assertEqual(response.status_code, 403)

    def test_manager_allowed(self):
        make_manager(username='rc_manager_access')
        self.client.login(username='rc_manager_access', password=_PASSWORD)
        response = self.client.get('/monitoring/reconcile/')
        self.assertEqual(response.status_code, 200)


class ReconcileInventoryContentTest(TestCase):

    def setUp(self):
        make_manager(username='rc_mgr_content')
        self.client.login(username='rc_mgr_content', password=_PASSWORD)
        self.unit = make_unit('TU-RC-CONTENT-001', crop_name='Cassava',
                               location_text='Bay 2', quantity=12)

    def test_lists_active_unit_with_current_quantity_prefilled(self):
        response = self.client.get('/monitoring/reconcile/')
        self.assertContains(response, 'TU-RC-CONTENT-001')
        self.assertContains(response, 'value="12"')

    def test_archived_unit_not_listed(self):
        self.unit.is_active = False
        self.unit.save()
        response = self.client.get('/monitoring/reconcile/')
        self.assertNotContains(response, 'TU-RC-CONTENT-001')

    def test_location_filter_narrows_results(self):
        make_unit('TU-RC-CONTENT-002', location_text='Bay 9', quantity=3)
        response = self.client.get('/monitoring/reconcile/?location=Bay 2')
        self.assertContains(response, 'TU-RC-CONTENT-001')
        self.assertNotContains(response, 'TU-RC-CONTENT-002')

    def test_empty_state_when_no_units_match(self):
        response = self.client.get('/monitoring/reconcile/?location=NoSuchPlace')
        self.assertContains(response, 'No active units match')


class ReconcileInventoryPostTest(TestCase):

    def setUp(self):
        make_manager(username='rc_mgr_post')
        self.client.login(username='rc_mgr_post', password=_PASSWORD)
        self.unit = make_unit('TU-RC-POST-001', quantity=10)

    def test_changed_quantity_creates_recount_event(self):
        self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': '7'})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 7)
        event = QuantityEvent.objects.get(tracking_unit=self.unit)
        self.assertEqual(event.event_type, QuantityEvent.EVENT_TYPE_RECOUNT)
        self.assertEqual(event.quantity_before, 10)
        self.assertEqual(event.quantity_change, -3)
        self.assertEqual(event.quantity_after, 7)

    def test_unchanged_quantity_creates_no_event(self):
        self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': '10'})
        self.assertFalse(QuantityEvent.objects.filter(tracking_unit=self.unit).exists())

    def test_blank_quantity_is_skipped(self):
        self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': ''})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 10)

    def test_negative_result_is_rejected(self):
        response = self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': '-5'})
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 10)

    def test_non_numeric_value_shows_error_and_is_skipped(self):
        response = self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 10)

    def test_success_message_shown_after_reconciliation(self):
        response = self.client.post(
            '/monitoring/reconcile/', {f'qty_{self.unit.pk}': '5'}, follow=True
        )
        self.assertContains(response, 'Reconciled 1 unit')

    def test_observer_cannot_post(self):
        make_observer(username='rc_post_obs')
        self.client.login(username='rc_post_obs', password=_PASSWORD)
        response = self.client.post('/monitoring/reconcile/', {f'qty_{self.unit.pk}': '5'})
        self.assertEqual(response.status_code, 403)


def make_position(code='POS-VIEW-001'):
    site = Site.objects.create(name=f'Site for {code}')
    sh = ScreenHouse.objects.create(site=site, name='SH1')
    bench = Bench.objects.create(screen_house=sh, name='Bench A')
    return Position.objects.create(bench=bench, code=code)


class EnvironmentalLogAccessTest(TestCase):

    def setUp(self):
        make_observer(username='env_obs_access')

    def test_anonymous_redirected_to_login(self):
        response = self.client.get('/monitoring/environmental-logs/record/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_observer_gets_200_on_record_form(self):
        self.client.login(username='env_obs_access', password=_PASSWORD)
        response = self.client.get('/monitoring/environmental-logs/record/')
        self.assertEqual(response.status_code, 200)

    def test_observer_gets_200_on_list(self):
        self.client.login(username='env_obs_access', password=_PASSWORD)
        response = self.client.get('/monitoring/environmental-logs/')
        self.assertEqual(response.status_code, 200)


class EnvironmentalLogPostTest(TestCase):

    def setUp(self):
        make_observer(username='env_obs_post')
        self.client.login(username='env_obs_post', password=_PASSWORD)
        self.position = make_position('POS-VIEW-POST-001')

    def _post(self, **overrides):
        data = {
            'position': str(self.position.pk),
            'temperature_c': '24.5',
            'humidity_pct': '60',
            'light_lux': '1200',
            'notes': '',
        }
        data.update(overrides)
        return self.client.post('/monitoring/environmental-logs/record/', data)

    def test_valid_post_creates_log(self):
        self._post()
        self.assertEqual(EnvironmentalLog.objects.filter(position=self.position).count(), 1)

    def test_valid_post_redirects_to_list(self):
        response = self._post()
        self.assertRedirects(response, '/monitoring/environmental-logs/')

    def test_no_readings_is_rejected(self):
        response = self._post(temperature_c='', humidity_pct='', light_lux='')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EnvironmentalLog.objects.count(), 0)

    def test_position_is_optional(self):
        response = self._post(position='')
        self.assertRedirects(response, '/monitoring/environmental-logs/')
        log = EnvironmentalLog.objects.get()
        self.assertIsNone(log.position)
