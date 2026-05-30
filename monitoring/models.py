from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from inventory.models import TrackingUnit


class Observation(models.Model):

    OBSERVATION_TYPE_ROUTINE = 'routine'
    OBSERVATION_TYPE_ISSUE = 'issue'
    OBSERVATION_TYPE_FOLLOW_UP = 'follow_up'
    OBSERVATION_TYPE_CORRECTION = 'correction'
    OBSERVATION_TYPE_FINAL = 'final'
    OBSERVATION_TYPE_CHOICES = [
        (OBSERVATION_TYPE_ROUTINE, 'Routine'),
        (OBSERVATION_TYPE_ISSUE, 'Issue'),
        (OBSERVATION_TYPE_FOLLOW_UP, 'Follow Up'),
        (OBSERVATION_TYPE_CORRECTION, 'Correction'),
        (OBSERVATION_TYPE_FINAL, 'Final'),
    ]

    STATUS_HEALTHY = 'healthy'
    STATUS_WATCH = 'watch'
    STATUS_SICK = 'sick'
    STATUS_CRITICAL = 'critical'
    STATUS_DEAD = 'dead'
    STATUS_RECOVERED = 'recovered'
    STATUS_CHOICES = [
        (STATUS_HEALTHY, 'Healthy'),
        (STATUS_WATCH, 'Watch'),
        (STATUS_SICK, 'Sick'),
        (STATUS_CRITICAL, 'Critical'),
        (STATUS_DEAD, 'Dead'),
        (STATUS_RECOVERED, 'Recovered'),
    ]

    tracking_unit = models.ForeignKey(
        TrackingUnit,
        on_delete=models.CASCADE,
        related_name='observations',
    )
    observation_type = models.CharField(
        max_length=20,
        choices=OBSERVATION_TYPE_CHOICES,
        default=OBSERVATION_TYPE_ROUTINE,
    )
    # Points to the observation this record corrects; required when
    # observation_type is 'correction'.
    corrects_observation = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='corrections',
    )
    observed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    growth_stage = models.CharField(max_length=100, blank=True)
    affected_quantity = models.PositiveIntegerField(blank=True, null=True)
    affected_zone = models.CharField(max_length=100, blank=True)
    water_condition = models.CharField(max_length=100, blank=True)
    pest_signs = models.CharField(max_length=255, blank=True)
    disease_signs = models.CharField(max_length=255, blank=True)
    action_taken = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_observations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tracking_unit.unit_code} — {self.get_status_display()} ({self.observed_at})'

    def clean(self):
        errors = {}

        if (
            self.observation_type == self.OBSERVATION_TYPE_CORRECTION
            and not self.corrects_observation_id
        ):
            errors['corrects_observation'] = (
                'A correction observation must reference the observation it corrects.'
            )

        if self.affected_quantity is not None and self.tracking_unit_id:
            try:
                unit_quantity = TrackingUnit.objects.values_list(
                    'quantity', flat=True
                ).get(pk=self.tracking_unit_id)
                if self.affected_quantity > unit_quantity:
                    errors['affected_quantity'] = (
                        f'Affected quantity ({self.affected_quantity}) cannot exceed '
                        f'tracking unit quantity ({unit_quantity}).'
                    )
            except TrackingUnit.DoesNotExist:
                pass

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                'Observations are immutable. Create a correction observation instead.'
            )
        super().save(*args, **kwargs)


_ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif']


class ObservationPhoto(models.Model):

    observation = models.ForeignKey(
        Observation,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    image = models.ImageField(
        upload_to='observation_photos/',
        validators=[FileExtensionValidator(allowed_extensions=_ALLOWED_IMAGE_EXTENSIONS)],
    )
    # Thumbnail is stored here once generated; generation is a later ticket.
    thumbnail = models.ImageField(
        upload_to='observation_thumbnails/',
        blank=True,
        null=True,
    )
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'Photo for {self.observation} ({self.uploaded_at})'


class QuantityEvent(models.Model):

    EVENT_TYPE_INITIAL = 'initial'
    EVENT_TYPE_DEATH = 'death'
    EVENT_TYPE_RECOUNT = 'recount'
    EVENT_TYPE_CORRECTION = 'correction'
    EVENT_TYPE_LOSS = 'loss'
    EVENT_TYPE_CHOICES = [
        (EVENT_TYPE_INITIAL, 'Initial'),
        (EVENT_TYPE_DEATH, 'Death / Culling'),
        (EVENT_TYPE_RECOUNT, 'Recount'),
        (EVENT_TYPE_CORRECTION, 'Correction'),
        (EVENT_TYPE_LOSS, 'Loss'),
    ]

    tracking_unit = models.ForeignKey(
        TrackingUnit,
        on_delete=models.CASCADE,
        related_name='quantity_events',
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    quantity_before = models.PositiveIntegerField()
    quantity_change = models.IntegerField()
    quantity_after = models.PositiveIntegerField()
    reason = models.TextField(blank=True)
    event_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_quantity_events',
    )

    class Meta:
        ordering = ['-event_date']

    def __str__(self):
        return (
            f'{self.tracking_unit.unit_code} — {self.get_event_type_display()} '
            f'({self.quantity_before} → {self.quantity_after})'
        )

    def clean(self):
        errors = {}

        if (
            self.quantity_before is not None
            and self.quantity_change is not None
            and self.quantity_after is not None
        ):
            expected = self.quantity_before + self.quantity_change

            if expected < 0:
                errors['quantity_change'] = (
                    f'Quantity change would result in a negative quantity '
                    f'({self.quantity_before} + {self.quantity_change} = {expected}). '
                    f'Quantity cannot go below zero.'
                )
            elif self.quantity_after != expected:
                errors['quantity_after'] = (
                    f'quantity_after ({self.quantity_after}) must equal '
                    f'quantity_before + quantity_change '
                    f'({self.quantity_before} + {self.quantity_change} = {expected}).'
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                'Quantity events are immutable. Create a new quantity event instead.'
            )
        super().save(*args, **kwargs)
