from io import BytesIO, StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
import datetime

from PIL import Image

from inventory.models import TrackingUnit
from monitoring.models import Observation, ObservationPhoto


def make_unit(unit_code='TU-CMD-001'):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Command Test Crop',
        quantity=5,
    )


def make_observation(unit):
    return Observation.objects.create(
        tracking_unit=unit,
        status=Observation.STATUS_HEALTHY,
    )


def make_image_file(name='photo.jpg', size=(2000, 2000), color='green', quality=95):
    img = Image.new('RGB', size, color=color)
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


def make_photo(observation, **kwargs):
    image_kwargs = {k: kwargs.pop(k) for k in ('name', 'size', 'color', 'quality') if k in kwargs}
    photo = ObservationPhoto.objects.create(
        observation=observation,
        image=make_image_file(**image_kwargs),
        **kwargs,
    )
    return photo


def backdate(photo, days):
    ObservationPhoto.objects.filter(pk=photo.pk).update(
        uploaded_at=timezone.now() - datetime.timedelta(days=days)
    )
    photo.refresh_from_db()
    return photo


class CompressOldObservationPhotosCommandTest(TestCase):

    def _call(self, **options):
        out = StringIO()
        call_command('compress_old_observation_photos', stdout=out, **options)
        return out.getvalue()

    def test_compresses_large_old_photo(self):
        unit = make_unit('TU-CMD-COMPRESS-001')
        obs = make_observation(unit)
        photo = make_photo(obs, name='old.jpg', size=(2000, 2000))
        backdate(photo, days=200)

        output = self._call(older_than_days=180, max_size_kb=0)

        photo.refresh_from_db()
        with Image.open(photo.image.path) as img:
            self.assertLessEqual(max(img.size), 1600)
        self.assertIn('Compressed', output)

    def test_recent_photo_is_not_touched(self):
        unit = make_unit('TU-CMD-RECENT-001')
        obs = make_observation(unit)
        photo = make_photo(obs, name='recent.jpg', size=(2000, 2000))
        original_name = photo.image.name

        self._call(older_than_days=180, max_size_kb=0)

        photo.refresh_from_db()
        self.assertEqual(photo.image.name, original_name)
        with Image.open(photo.image.path) as img:
            self.assertEqual(img.size, (2000, 2000))

    def test_already_small_photo_is_skipped(self):
        unit = make_unit('TU-CMD-SMALL-001')
        obs = make_observation(unit)
        photo = make_photo(obs, name='small.jpg', size=(50, 50))
        backdate(photo, days=200)
        original_name = photo.image.name

        output = self._call(older_than_days=180, max_size_kb=10_000)

        photo.refresh_from_db()
        self.assertEqual(photo.image.name, original_name)
        self.assertIn('Skipped (already small): 1', output)

    def test_heic_extension_is_skipped(self):
        unit = make_unit('TU-CMD-HEIC-001')
        obs = make_observation(unit)
        photo = ObservationPhoto.objects.create(
            observation=obs,
            image=SimpleUploadedFile('photo.heic', b'not-a-real-heic-file', content_type='image/heic'),
        )
        backdate(photo, days=200)
        original_name = photo.image.name

        output = self._call(older_than_days=180, max_size_kb=0)

        photo.refresh_from_db()
        self.assertEqual(photo.image.name, original_name)
        self.assertIn('Skipped (unsupported format): 1', output)

    def test_dry_run_does_not_modify_file(self):
        unit = make_unit('TU-CMD-DRYRUN-001')
        obs = make_observation(unit)
        photo = make_photo(obs, name='dryrun.jpg', size=(2000, 2000))
        backdate(photo, days=200)
        original_name = photo.image.name

        output = self._call(older_than_days=180, max_size_kb=0, dry_run=True)

        photo.refresh_from_db()
        self.assertEqual(photo.image.name, original_name)
        with Image.open(photo.image.path) as img:
            self.assertEqual(img.size, (2000, 2000))
        self.assertIn('Would compress', output)
        self.assertIn('dry run', output)
