from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from inventory.models import TrackingUnit
from monitoring.models import Observation, ObservationPhoto, QuantityEvent


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
        image = SimpleUploadedFile('plant.jpg', b'\xff\xd8\xff', content_type='image/jpeg')
        photo = ObservationPhoto(observation=obs, image=image)
        self.assertEqual(photo.observation, obs)

    def test_valid_image_extension_passes_validation(self):
        obs = self._make_observation()
        for ext in ['jpg', 'jpeg', 'png', 'webp']:
            image = SimpleUploadedFile(f'plant.{ext}', b'fake', content_type='image/jpeg')
            photo = ObservationPhoto(observation=obs, image=image)
            # Should not raise for extension check; ImageField content validation
            # is form-level and not triggered by full_clean() on the model.
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
        # quantity_before=3, quantity_change=-5 => would be -2
        # quantity_after cannot be set to -2 (PositiveIntegerField), so we
        # set it to 0 which is wrong by the math — both routes raise ValidationError.
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
        # quantity_after can still be zero here because the model's explicit
        # negative-result check runs before the equality mismatch branch.
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
