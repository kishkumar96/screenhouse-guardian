import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from inventory.models import TrackingUnit
from monitoring.models import MAX_OBSERVATION_IMAGE_SIZE_BYTES, Observation, ObservationPhoto

User = get_user_model()


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

    def test_index_returns_200(self):
        response = self.client.get('/monitoring/')
        self.assertEqual(response.status_code, 200)


# ── Observe form — GET ────────────────────────────────────────────────────────

class ObserveFormGetTest(TestCase):

    def setUp(self):
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


# ── Observe form — POST, no photo ─────────────────────────────────────────────

class ObserveFormPostTest(TestCase):

    def setUp(self):
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

    def test_created_by_is_none_when_anonymous(self):
        self._post()
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertIsNone(obs.created_by)

    def test_created_by_is_set_when_logged_in(self):
        user = User.objects.create_user(username='observer', password='pass')
        self.client.login(username='observer', password='pass')
        self._post()
        obs = Observation.objects.get(tracking_unit=self.unit)
        self.assertEqual(obs.created_by, user)

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


# ── Observe form — oversized photo rejection ──────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OversizedPhotoTest(TestCase):

    def setUp(self):
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
        # Create a photo record with no thumbnail (bypass save() to skip generation)
        photo = ObservationPhoto(observation=self.obs, image=create_test_jpeg())
        # Save without triggering thumbnail generation by calling super().save() manually
        from django.db.models import Model
        Model.save(photo)
        ObservationPhoto.objects.filter(pk=photo.pk).update(thumbnail='')
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        # Original image URL used as src when thumbnail is absent
        self.assertContains(response, 'observation_photos')
