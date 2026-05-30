from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import TrackingUnit


@admin.register(TrackingUnit)
class TrackingUnitAdmin(admin.ModelAdmin):
    list_display = [
        'unit_code',
        'unit_type',
        'container_type',
        'crop_name',
        'quantity',
        'location_text',
        'is_active',
        'created_at',
    ]
    list_filter = ['unit_type', 'container_type', 'is_active']
    search_fields = ['unit_code', 'crop_name', 'accession_code', 'batch_code', 'location_text']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'qr_label_link']
    ordering = ['-created_at']
    fieldsets = [
        ('Identity', {
            'fields': ['unit_code', 'unit_type', 'container_type'],
        }),
        ('Crop information', {
            'fields': ['crop_name', 'accession_code', 'batch_code'],
        }),
        ('Location & quantity', {
            'fields': ['location_text', 'quantity'],
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
