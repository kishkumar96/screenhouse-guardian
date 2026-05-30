from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Accession, Batch, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ['name', 'scientific_name', 'category', 'is_active', 'created_at']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'scientific_name']
    readonly_fields = ['created_by', 'created_at', 'updated_at']

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Accession)
class AccessionAdmin(admin.ModelAdmin):
    list_display = ['accession_code', 'crop', 'source_country', 'source_organisation', 'is_active', 'created_at']
    list_filter = ['is_active', 'crop']
    search_fields = ['accession_code', 'source_country', 'source_organisation']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    raw_id_fields = ['crop']

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['batch_code', 'accession', 'source_type', 'received_date', 'initial_quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'source_type']
    search_fields = ['batch_code', 'accession__accession_code']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    raw_id_fields = ['accession']

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(ScreenHouse)
class ScreenHouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'site', 'is_active']
    list_filter = ['is_active', 'site']
    search_fields = ['name', 'site__name']
    raw_id_fields = ['site']


@admin.register(Bench)
class BenchAdmin(admin.ModelAdmin):
    list_display = ['name', 'screen_house', 'is_active']
    list_filter = ['is_active', 'screen_house__site']
    search_fields = ['name', 'screen_house__name']
    raw_id_fields = ['screen_house']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['code', 'bench', 'is_active']
    list_filter = ['is_active', 'bench__screen_house__site']
    search_fields = ['code', 'bench__name']
    raw_id_fields = ['bench']


@admin.register(TrackingUnit)
class TrackingUnitAdmin(admin.ModelAdmin):
    list_display = [
        'unit_code',
        'unit_type',
        'display_crop',
        'display_accession',
        'display_location',
        'quantity',
        'is_active',
        'created_at',
    ]
    list_filter = ['unit_type', 'container_type', 'is_active', 'archive_reason']
    search_fields = ['unit_code', 'crop_name', 'accession_code', 'batch_code', 'location_text']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'qr_label_link']
    ordering = ['-created_at']
    fieldsets = [
        ('Identity', {
            'fields': ['unit_code', 'unit_type', 'container_type'],
        }),
        ('Legacy crop / location (Phase 1A)', {
            'fields': ['crop_name', 'accession_code', 'batch_code', 'location_text'],
            'description': 'These text fields are preserved for QR label and export compatibility.',
        }),
        ('Structured inventory (Phase 1B)', {
            'fields': ['crop', 'accession', 'batch', 'position'],
            'classes': ['collapse'],
            'description': 'Link to structured models. Falls back to legacy text fields when empty.',
        }),
        ('Quantity', {
            'fields': ['quantity'],
        }),
        ('QR code', {
            'fields': ['qr_code', 'qr_label_link'],
            'classes': ['collapse'],
        }),
        ('Archive', {
            'fields': ['is_active', 'archived_at', 'archive_reason'],
            'classes': ['collapse'],
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def qr_label_link(self, obj):
        if not obj.pk:
            return '—'
        url = reverse('qr:label', kwargs={'unit_code': obj.unit_code})
        return format_html('<a href="{}" target="_blank">View / Print Label</a>', url)

    qr_label_link.short_description = 'QR label'

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.extend(['unit_code', 'quantity', 'qr_code'])
        return readonly_fields

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
