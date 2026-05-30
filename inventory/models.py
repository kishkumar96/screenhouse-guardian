from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TrackingUnit(models.Model):

    UNIT_TYPE_CONTAINER = 'container'
    UNIT_TYPE_INDIVIDUAL = 'individual'
    UNIT_TYPE_CHOICES = [
        (UNIT_TYPE_CONTAINER, 'Container'),
        (UNIT_TYPE_INDIVIDUAL, 'Individual'),
    ]

    CONTAINER_TYPE_TRAY = 'tray'
    CONTAINER_TYPE_POT = 'pot'
    CONTAINER_TYPE_NURSERY_BAG = 'nursery_bag'
    CONTAINER_TYPE_SEEDLING_TRAY = 'seedling_tray'
    CONTAINER_TYPE_OTHER = 'other'
    CONTAINER_TYPE_CHOICES = [
        (CONTAINER_TYPE_TRAY, 'Tray'),
        (CONTAINER_TYPE_POT, 'Pot'),
        (CONTAINER_TYPE_NURSERY_BAG, 'Nursery Bag'),
        (CONTAINER_TYPE_SEEDLING_TRAY, 'Seedling Tray'),
        (CONTAINER_TYPE_OTHER, 'Other'),
    ]

    unit_code = models.CharField(max_length=50, unique=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES)
    container_type = models.CharField(
        max_length=20,
        choices=CONTAINER_TYPE_CHOICES,
        blank=True,
    )
    crop_name = models.CharField(max_length=200)
    accession_code = models.CharField(max_length=100, blank=True)
    batch_code = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    location_text = models.CharField(max_length=255, blank=True)
    # qr_code image is generated and stored here; see qr app (Phase 1A next ticket)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    archive_reason = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tracking_units',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.unit_code} ({self.get_unit_type_display()})'

    def clean(self):
        errors = {}

        if self.unit_type == self.UNIT_TYPE_INDIVIDUAL and self.quantity > 1:
            errors['quantity'] = (
                'Individual tracking units must have a quantity of 1. '
                'Use a container type for groups of plants.'
            )
        if (
            self.unit_type == self.UNIT_TYPE_INDIVIDUAL
            and self.container_type
        ):
            errors['container_type'] = (
                'Individual tracking units must not have a container type.'
            )

        if errors:
            raise ValidationError(errors)
