import datetime
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from inventory.models import TrackingUnit
from monitoring.models import (
    MAX_OBSERVATION_IMAGE_SIZE_BYTES,
    Observation,
    ObservationPhoto,
    QuantityEvent,
    Treatment,
)


def make_container(unit_code='TU-MON-001', quantity=10):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=quantity,
    )


def make_observation(unit, **overrides):
    """Return an unsaved Observation with sensible defaults."""
    defaults = dict(
        tracking_unit=unit,
        observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
        status=Observation.STATUS_HEALTHY,
    )
    defaults.update(overrides)
    return Observation(**defaults)


def make_real_jpeg(filename='plant.jpg', width=10, height=10):
    """Return a SimpleUploadedFile containing a valid minimal JPEG."""
    from PIL import Image
    img = Image.new('RGB', (width, height), color='green')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.read(), content_type='image/jpeg')


def make_real_png(filename='plant.png'):
    """Return a SimpleUploadedFile containing a valid minimal PNG."""
    from PIL import Image
    img = Image.new('RGB', (10, 10), color='blue')
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.read(), content_type='image/png')


# ── Observation creation ──────────────────────────────────────────────────────

class ObservationCreationTest(TestCase):

    def test_can_create_routine_observation(self):
        unit = make_container('TU-OBS-001')
        obs = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
            notes='Looking good.',
        )
        self.assertEqual(obs.tracking_unit, unit)
        self.assertEqual(obs.status, Observation.STATUS_HEALTHY)

    def test_str_representation(self):
        unit = make_container('TU-OBS-STR')
        obs = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
        )
        self.assertIn(unit.unit_code, str(obs))

    def test_saved_observation_cannot_be_edited(self):
        unit = make_container('TU-OBS-IMM-001')
        obs = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
            notes='Original note',
        )
        obs.notes = 'Changed note'
        with self.assertRaises(ValidationError):
            obs.save()


# ── Correction observations ───────────────────────────────────────────────────

class CorrectionObservationTest(TestCase):

    def test_correction_without_corrects_observation_raises_error(self):
        unit = make_container('TU-CORR-001')
        obs = make_observation(
            unit,
            observation_type=Observation.OBSERVATION_TYPE_CORRECTION,
            status=Observation.STATUS_HEALTHY,
        )
        with self.assertRaises(ValidationError) as ctx:
            obs.full_clean()
        self.assertIn('corrects_observation', ctx.exception.message_dict)

    def test_correction_with_corrects_observation_is_valid(self):
        unit = make_container('TU-CORR-002')
        original = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_SICK,
        )
        correction = make_observation(
            unit,
            observation_type=Observation.OBSERVATION_TYPE_CORRECTION,
            status=Observation.STATUS_HEALTHY,
            corrects_observation=original,
        )
        # Should not raise
        correction.full_clean()

    def test_routine_observation_does_not_require_corrects_observation(self):
        unit = make_container('TU-CORR-003')
        obs = make_observation(unit, observation_type=Observation.OBSERVATION_TYPE_ROUTINE)
        obs.full_clean()

    def test_correction_references_correct_observation(self):
        unit = make_container('TU-CORR-004')
        original = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_SICK,
        )
        correction = Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_CORRECTION,
            status=Observation.STATUS_HEALTHY,
            corrects_observation=original,
        )
        self.assertEqual(correction.corrects_observation, original)
        self.assertIn(correction, original.corrections.all())


# ── Affected quantity validation ──────────────────────────────────────────────

class ObservationAffectedQuantityTest(TestCase):

    def test_affected_quantity_within_unit_quantity_is_valid(self):
        unit = make_container('TU-AQ-001', quantity=10)
        obs = make_observation(unit, affected_quantity=5)
        obs.full_clean()

    def test_affected_quantity_equal_to_unit_quantity_is_valid(self):
        unit = make_container('TU-AQ-002', quantity=10)
        obs = make_observation(unit, affected_quantity=10)
        obs.full_clean()

    def test_affected_quantity_exceeding_unit_quantity_raises_error(self):
        unit = make_container('TU-AQ-003', quantity=10)
        obs = make_observation(unit, affected_quantity=11)
        with self.assertRaises(ValidationError) as ctx:
            obs.full_clean()
        self.assertIn('affected_quantity', ctx.exception.message_dict)

    def test_no_affected_quantity_is_valid(self):
        unit = make_container('TU-AQ-004', quantity=10)
        obs = make_observation(unit, affected_quantity=None)
        obs.full_clean()


# ── ObservationPhoto — extension and link tests ───────────────────────────────

class ObservationPhotoTest(TestCase):

    def _make_observation(self):
        unit = make_container('TU-PHOTO-001')
        return Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
        )

    def test_photo_links_to_observation(self):
        obs = self._make_observation()
        # Just building the instance — not saving, so validators do not run.
        image = SimpleUploadedFile('plant.jpg', b'\xff\xd8\xff', content_type='image/jpeg')
        photo = ObservationPhoto(observation=obs, image=image)
        self.assertEqual(photo.observation, obs)

    def test_valid_image_extension_passes_validation(self):
        """Extension validator accepts jpg/jpeg/png/webp; content validator requires real image."""
        obs = self._make_observation()
        for ext, fmt in [('jpg', 'JPEG'), ('jpeg', 'JPEG'), ('png', 'PNG')]:
            from PIL import Image
            img = Image.new('RGB', (10, 10), color='green')
            buf = BytesIO()
            img.save(buf, format=fmt)
            buf.seek(0)
            image = SimpleUploadedFile(f'plant.{ext}', buf.read(), content_type=f'image/{fmt.lower()}')
            photo = ObservationPhoto(observation=obs, image=image)
            # Should not raise — extension, size, and content are all valid
            photo.image.field.run_validators(photo.image)

    def test_invalid_file_extension_raises_validation_error(self):
        obs = self._make_observation()
        bad_file = SimpleUploadedFile('document.txt', b'not an image', content_type='text/plain')
        photo = ObservationPhoto(observation=obs, image=bad_file)
        with self.assertRaises(ValidationError):
            photo.image.field.run_validators(photo.image)

    def test_invalid_extension_pdf_raises_validation_error(self):
        obs = self._make_observation()
        bad_file = SimpleUploadedFile('report.pdf', b'%PDF', content_type='application/pdf')
        photo = ObservationPhoto(observation=obs, image=bad_file)
        with self.assertRaises(ValidationError):
            photo.image.field.run_validators(photo.image)

    def test_heic_extension_passes_extension_validator(self):
        obs = self._make_observation()
        heic_file = SimpleUploadedFile('photo.heic', b'fake heic content', content_type='image/heic')
        photo = ObservationPhoto(observation=obs, image=heic_file)
        # Extension validator alone must accept .heic
        from django.core.validators import FileExtensionValidator
        from monitoring.models import _ALLOWED_IMAGE_EXTENSIONS
        validator = FileExtensionValidator(allowed_extensions=_ALLOWED_IMAGE_EXTENSIONS)
        validator(photo.image)  # must not raise

    def test_heif_extension_passes_extension_validator(self):
        obs = self._make_observation()
        heif_file = SimpleUploadedFile('photo.heif', b'fake heif content', content_type='image/heif')
        photo = ObservationPhoto(observation=obs, image=heif_file)
        from django.core.validators import FileExtensionValidator
        from monitoring.models import _ALLOWED_IMAGE_EXTENSIONS
        validator = FileExtensionValidator(allowed_extensions=_ALLOWED_IMAGE_EXTENSIONS)
        validator(photo.image)  # must not raise

    def test_heic_content_validator_skips_pillow(self):
        obs = self._make_observation()
        # Deliberately non-image bytes — validator must not raise for .heic
        heic_file = SimpleUploadedFile('photo.heic', b'not a real image', content_type='image/heic')
        photo = ObservationPhoto(observation=obs, image=heic_file)
        from monitoring.models import validate_observation_image_content
        validate_observation_image_content(photo.image)  # must not raise


# ── ObservationPhoto — size and content validators ────────────────────────────

class ObservationPhotoValidationTest(TestCase):

    def _make_obs(self):
        unit = make_container('TU-VAL-001')
        return Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
        )

    def test_rejects_file_exceeding_max_size(self):
        obs = self._make_obs()
        oversized = SimpleUploadedFile(
            'big.jpg',
            b'x' * (MAX_OBSERVATION_IMAGE_SIZE_BYTES + 1),
            content_type='image/jpeg',
        )
        photo = ObservationPhoto(observation=obs, image=oversized)
        with self.assertRaises(ValidationError) as ctx:
            photo.image.field.run_validators(photo.image)
        self.assertIn('too large', str(ctx.exception))

    def test_accepts_valid_jpeg_under_max_size(self):
        obs = self._make_obs()
        jpeg = make_real_jpeg('small.jpg')
        photo = ObservationPhoto(observation=obs, image=jpeg)
        # Should not raise
        photo.image.field.run_validators(photo.image)

    def test_rejects_invalid_image_content_with_jpg_extension(self):
        obs = self._make_obs()
        fake = SimpleUploadedFile('fake.jpg', b'this is not an image', content_type='image/jpeg')
        photo = ObservationPhoto(observation=obs, image=fake)
        with self.assertRaises(ValidationError):
            photo.image.field.run_validators(photo.image)


# ── ObservationPhoto — thumbnail generation ───────────────────────────────────

@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ObservationPhotoThumbnailTest(TestCase):

    def _make_obs(self):
        unit = make_container('TU-THUMB-001')
        return Observation.objects.create(
            tracking_unit=unit,
            observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
            status=Observation.STATUS_HEALTHY,
        )

    def test_generates_thumbnail_for_valid_jpeg(self):
        obs = self._make_obs()
        photo = ObservationPhoto.objects.create(
            observation=obs,
            image=make_real_jpeg('thumb_test.jpg'),
        )
        photo.refresh_from_db()
        self.assertTrue(bool(photo.thumbnail))

    def test_thumbnail_field_is_populated_after_save(self):
        obs = self._make_obs()
        photo = ObservationPhoto.objects.create(
            observation=obs,
            image=make_real_jpeg('pop_test.jpg'),
        )
        photo.refresh_from_db()
        self.assertIn('observation_thumbnails', photo.thumbnail.name)

    def test_generates_thumbnail_for_valid_png(self):
        obs = self._make_obs()
        photo = ObservationPhoto.objects.create(
            observation=obs,
            image=make_real_png('thumb_test.png'),
        )
        photo.refresh_from_db()
        self.assertTrue(bool(photo.thumbnail))

    def test_thumbnail_is_smaller_or_equal_to_max_dimensions(self):
        obs = self._make_obs()
        # Use a large-ish image so thumbnail actually needs to resize
        from PIL import Image as PILImage
        large = PILImage.new('RGB', (800, 600), color='red')
        buf = BytesIO()
        large.save(buf, format='JPEG')
        buf.seek(0)
        big_file = SimpleUploadedFile('big_plant.jpg', buf.read(), content_type='image/jpeg')
        photo = ObservationPhoto.objects.create(observation=obs, image=big_file)
        photo.refresh_from_db()
        self.assertTrue(bool(photo.thumbnail))
        with PILImage.open(photo.thumbnail.path) as thumb_img:
            w, h = thumb_img.size
        self.assertLessEqual(w, 400)
        self.assertLessEqual(h, 400)


# ── QuantityEvent creation ────────────────────────────────────────────────────

class QuantityEventCreationTest(TestCase):

    def test_can_create_quantity_event(self):
        unit = make_container('TU-QE-001', quantity=50)
        event = QuantityEvent.objects.create(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=50,
            quantity_change=-4,
            quantity_after=46,
        )
        self.assertEqual(event.quantity_after, 46)
        self.assertEqual(event.tracking_unit, unit)

    def test_str_representation(self):
        unit = make_container('TU-QE-STR', quantity=10)
        event = QuantityEvent.objects.create(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=10,
            quantity_change=-2,
            quantity_after=8,
        )
        self.assertIn(unit.unit_code, str(event))

    def test_saved_quantity_event_cannot_be_edited(self):
        unit = make_container('TU-QE-IMM-001', quantity=10)
        event = QuantityEvent.objects.create(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=10,
            quantity_change=-2,
            quantity_after=8,
        )
        event.reason = 'Edited reason'
        with self.assertRaises(ValidationError):
            event.save()


# ── QuantityEvent validation ──────────────────────────────────────────────────

class QuantityEventValidationTest(TestCase):

    def test_quantity_after_must_equal_before_plus_change(self):
        unit = make_container('TU-QEV-001', quantity=50)
        event = QuantityEvent(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=50,
            quantity_change=-4,
            quantity_after=99,  # wrong: should be 46
        )
        with self.assertRaises(ValidationError) as ctx:
            event.full_clean()
        self.assertIn('quantity_after', ctx.exception.message_dict)

    def test_valid_quantity_event_passes_clean(self):
        unit = make_container('TU-QEV-002', quantity=50)
        event = QuantityEvent(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=50,
            quantity_change=-4,
            quantity_after=46,
        )
        event.full_clean()

    def test_quantity_after_zero_is_valid_when_math_correct(self):
        unit = make_container('TU-QEV-003', quantity=5)
        event = QuantityEvent(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=5,
            quantity_change=-5,
            quantity_after=0,
        )
        event.full_clean()

    def test_quantity_change_resulting_in_negative_raises_error(self):
        unit = make_container('TU-QEV-004', quantity=3)
        event = QuantityEvent(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=3,
            quantity_change=-5,
            quantity_after=0,  # doesn't match 3 + (-5) = -2
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_negative_result_detected_by_clean(self):
        """clean() explicitly rejects when before + change < 0."""
        unit = make_container('TU-QEV-005', quantity=10)
        event = QuantityEvent(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_before=3,
            quantity_change=-5,
            quantity_after=0,
        )
        with self.assertRaises(ValidationError) as ctx:
            event.full_clean()
        self.assertIn('quantity_change', ctx.exception.message_dict)


# ── Treatment model ───────────────────────────────────────────────────────────

def make_treatment(unit, **overrides):
    defaults = dict(
        tracking_unit=unit,
        treatment_type=Treatment.TYPE_WATERED,
        reason='Regular watering cycle',
    )
    defaults.update(overrides)
    return Treatment(**defaults)


class TreatmentCreationTest(TestCase):

    def setUp(self):
        self.unit = make_container('TU-TX-001')

    def test_can_create_treatment(self):
        tx = Treatment.objects.create(
            tracking_unit=self.unit,
            treatment_type=Treatment.TYPE_FUNGICIDE,
            reason='Powdery mildew observed',
        )
        self.assertIsNotNone(tx.pk)

    def test_belongs_to_tracking_unit(self):
        tx = Treatment.objects.create(
            tracking_unit=self.unit,
            treatment_type=Treatment.TYPE_WATERED,
            reason='Dry soil',
        )
        self.assertEqual(tx.tracking_unit, self.unit)
        self.assertIn(tx, self.unit.treatments.all())

    def test_can_link_related_observation(self):
        obs = Observation.objects.create(
            tracking_unit=self.unit,
            observation_type=Observation.OBSERVATION_TYPE_ISSUE,
            status=Observation.STATUS_SICK,
        )
        tx = Treatment.objects.create(
            tracking_unit=self.unit,
            treatment_type=Treatment.TYPE_FUNGICIDE,
            reason='Responded to sick observation',
            related_observation=obs,
        )
        self.assertEqual(tx.related_observation, obs)

    def test_default_outcome_is_pending(self):
        tx = Treatment.objects.create(
            tracking_unit=self.unit,
            treatment_type=Treatment.TYPE_WATERED,
            reason='Test',
        )
        self.assertEqual(tx.outcome, Treatment.OUTCOME_PENDING)

    def test_str_includes_unit_code_and_type(self):
        tx = Treatment.objects.create(
            tracking_unit=self.unit,
            treatment_type=Treatment.TYPE_WATERED,
            reason='Test',
        )
        self.assertIn(self.unit.unit_code, str(tx))
        self.assertIn('Watered', str(tx))
