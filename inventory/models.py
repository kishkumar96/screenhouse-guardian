from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Crop(models.Model):
    name = models.CharField(max_length=200, unique=True)
    scientific_name = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_crops',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Accession(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name='accessions')
    accession_code = models.CharField(max_length=100, unique=True)
    source_country = models.CharField(max_length=100, blank=True)
    source_organisation = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_accessions',
    )

    class Meta:
        ordering = ['accession_code']

    def __str__(self):
        return self.accession_code


class Batch(models.Model):
    accession = models.ForeignKey(Accession, on_delete=models.CASCADE, related_name='batches')
    batch_code = models.CharField(max_length=100, unique=True)
    source_type = models.CharField(max_length=100, blank=True)
    received_date = models.DateField(null=True, blank=True)
    initial_quantity = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_batches',
    )

    class Meta:
        ordering = ['batch_code']

    def __str__(self):
        return self.batch_code


class Site(models.Model):
    name = models.CharField(max_length=200, unique=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ScreenHouse(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='screen_houses')
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['site', 'name']
        unique_together = [('site', 'name')]

    def __str__(self):
        return f'{self.site.name} / {self.name}'


class Bench(models.Model):
    screen_house = models.ForeignKey(ScreenHouse, on_delete=models.CASCADE, related_name='benches')
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['screen_house', 'name']
        unique_together = [('screen_house', 'name')]

    def __str__(self):
        return f'{self.screen_house} / {self.name}'


class Position(models.Model):
    bench = models.ForeignKey(Bench, on_delete=models.CASCADE, related_name='positions')
    code = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['bench', 'code']
        unique_together = [('bench', 'code')]

    def __str__(self):
        return f'{self.bench} / {self.code}'


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
    # Phase 1A legacy text fields — kept permanently for QR label compatibility
    crop_name = models.CharField(max_length=200)
    accession_code = models.CharField(max_length=100, blank=True)
    batch_code = models.CharField(max_length=100, blank=True)
    location_text = models.CharField(max_length=255, blank=True)

    # Phase 1B structured FKs — nullable so Phase 1A units remain valid
    crop = models.ForeignKey(
        Crop,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tracking_units',
    )
    accession = models.ForeignKey(
        Accession,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tracking_units',
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tracking_units',
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tracking_units',
    )

    quantity = models.PositiveIntegerField(default=1)
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

    def save(self, *args, **kwargs):
        if not self.is_active and self.archived_at is None:
            self.archived_at = timezone.now()
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'archived_at' not in update_fields:
                kwargs['update_fields'] = list(update_fields) + ['archived_at']
        super().save(*args, **kwargs)

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

    @property
    def display_crop(self):
        if self.crop_id:
            return self.crop.name
        return self.crop_name

    @property
    def display_accession(self):
        if self.accession_id:
            return self.accession.accession_code
        return self.accession_code

    @property
    def display_batch(self):
        if self.batch_id:
            return self.batch.batch_code
        return self.batch_code

    @property
    def display_location(self):
        if self.position_id:
            pos = self.position
            bench = pos.bench
            sh = bench.screen_house
            site = sh.site
            return f'{site.name} / {sh.name} / {bench.name} / {pos.code}'
        return self.location_text

    _ARCHIVE_REASON_LABELS = {
        'dead': 'Dead',
        'empty': 'Empty',
        'distributed': 'Distributed',
        'transferred': 'Transferred',
        'merged': 'Merged',
        'destroyed': 'Destroyed',
        'entered_by_mistake': 'Entered by mistake',
        'retired': 'Retired',
        'other': 'Other',
    }

    @property
    def archive_reason_display(self):
        return self._ARCHIVE_REASON_LABELS.get(self.archive_reason, self.archive_reason)
