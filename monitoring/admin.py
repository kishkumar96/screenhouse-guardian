from django.contrib import admin

from .models import DailyRound, DailyRoundItem, Observation, ObservationPhoto, QuantityEvent, Treatment


class ObservationPhotoInline(admin.TabularInline):
    model = ObservationPhoto
    extra = 0
    readonly_fields = ['uploaded_at']
    fields = ['image', 'thumbnail', 'caption', 'uploaded_at']


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_unit',
        'observation_type',
        'status',
        'affected_quantity',
        'observed_at',
        'created_by',
    ]
    list_filter = ['observation_type', 'status']
    search_fields = ['tracking_unit__unit_code', 'notes', 'action_taken']
    readonly_fields = ['created_by', 'observed_at', 'created_at']
    inlines = [ObservationPhotoInline]
    fieldsets = [
        ('Tracking unit', {
            'fields': ['tracking_unit', 'observation_type', 'corrects_observation'],
        }),
        ('Status', {
            'fields': ['status', 'growth_stage'],
        }),
        ('Detail', {
            'fields': [
                'affected_quantity',
                'affected_zone',
                'water_condition',
                'pest_signs',
                'disease_signs',
                'action_taken',
                'notes',
            ],
        }),
        ('Metadata', {
            'fields': ['created_by', 'observed_at', 'created_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.extend(
                field.name for field in self.model._meta.fields
                if field.name not in readonly_fields
            )
        return readonly_fields

    def get_inline_instances(self, request, obj=None):
        if obj:
            return []
        return super().get_inline_instances(request, obj)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or super().has_change_permission(
            request, obj
        )

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ObservationPhoto)
class ObservationPhotoAdmin(admin.ModelAdmin):
    list_display = ['observation', 'caption', 'uploaded_at']
    readonly_fields = ['uploaded_at']
    search_fields = ['observation__tracking_unit__unit_code', 'caption']

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.extend(
                field.name for field in self.model._meta.fields
                if field.name not in readonly_fields
            )
        return readonly_fields


@admin.register(QuantityEvent)
class QuantityEventAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_unit',
        'event_type',
        'quantity_before',
        'quantity_change',
        'quantity_after',
        'event_date',
        'created_by',
    ]
    list_filter = ['event_type']
    search_fields = ['tracking_unit__unit_code', 'reason']
    readonly_fields = ['created_by', 'event_date']
    fieldsets = [
        ('Event', {
            'fields': ['tracking_unit', 'event_type'],
        }),
        ('Quantity', {
            'fields': ['quantity_before', 'quantity_change', 'quantity_after'],
        }),
        ('Detail', {
            'fields': ['reason'],
        }),
        ('Metadata', {
            'fields': ['created_by', 'event_date'],
            'classes': ['collapse'],
        }),
    ]

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.extend(
                field.name for field in self.model._meta.fields
                if field.name not in readonly_fields
            )
        return readonly_fields

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or super().has_change_permission(
            request, obj
        )

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = [
        'tracking_unit',
        'treatment_type',
        'treatment_date',
        'follow_up_date',
        'outcome',
        'created_by',
    ]
    list_filter = ['treatment_type', 'outcome', 'follow_up_date']
    search_fields = ['tracking_unit__unit_code', 'reason', 'product_used', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Tracking unit', {
            'fields': ['tracking_unit', 'related_observation'],
        }),
        ('Treatment', {
            'fields': ['treatment_type', 'treatment_date', 'product_used', 'dose_rate', 'reason'],
        }),
        ('Follow-up', {
            'fields': ['follow_up_date', 'outcome', 'notes'],
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class DailyRoundItemInline(admin.TabularInline):
    model = DailyRoundItem
    extra = 0
    readonly_fields = ['completed_at', 'observation']
    fields = ['tracking_unit', 'completed', 'completed_at', 'observation', 'notes']
    show_change_link = True


@admin.register(DailyRound)
class DailyRoundAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'date', 'status', 'assigned_to',
        'item_count', 'completed_count', 'created_by',
    ]
    list_filter = ['status', 'date']
    search_fields = ['name', 'notes', 'location_filter']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DailyRoundItemInline]
    fieldsets = [
        ('Round', {
            'fields': ['name', 'date', 'status', 'assigned_to', 'location_filter', 'notes'],
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    @admin.display(description='Total items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Completed')
    def completed_count(self, obj):
        return obj.items.filter(completed=True).count()

    def save_model(self, request, obj, form, change):
        if obj.created_by_id is None and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DailyRoundItem)
class DailyRoundItemAdmin(admin.ModelAdmin):
    list_display = ['daily_round', 'tracking_unit', 'completed', 'completed_at', 'observation']
    list_filter = ['completed', 'daily_round__date']
    search_fields = ['tracking_unit__unit_code', 'daily_round__name', 'notes']
    readonly_fields = ['completed_at']
