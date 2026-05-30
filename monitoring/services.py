from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone

from inventory.models import TrackingUnit

from .models import DailyRound, DailyRoundItem, Observation, QuantityEvent


def apply_quantity_event(
    *,
    tracking_unit=None,
    tracking_unit_id=None,
    event_type,
    quantity_change,
    user,
    reason='',
):
    if tracking_unit is None and tracking_unit_id is None:
        raise ValidationError('tracking_unit or tracking_unit_id is required.')

    if tracking_unit is not None:
        if tracking_unit.pk is None:
            raise ValidationError('tracking_unit must be saved before applying a quantity event.')
        if tracking_unit_id is not None and tracking_unit_id != tracking_unit.pk:
            raise ValidationError('tracking_unit and tracking_unit_id must refer to the same row.')
        tracking_unit_id = tracking_unit.pk

    if isinstance(quantity_change, bool) or not isinstance(quantity_change, int):
        raise ValidationError({'quantity_change': 'quantity_change must be an integer.'})

    with transaction.atomic():
        unit = TrackingUnit.objects.select_for_update().get(pk=tracking_unit_id)

        quantity_before = unit.quantity
        quantity_after = quantity_before + quantity_change

        if quantity_after < 0:
            raise ValidationError(
                {'quantity_change': 'Quantity change would result in a negative quantity.'}
            )

        event = QuantityEvent(
            tracking_unit=unit,
            event_type=event_type,
            quantity_before=quantity_before,
            quantity_change=quantity_change,
            quantity_after=quantity_after,
            reason=reason,
            created_by=user,
        )
        event.full_clean()
        event.save()

        unit.quantity = quantity_after
        unit.save(update_fields=['quantity'])

        return event


# ── Daily round services ───────────────────────────────────────────────────────

MODE_ALL_ACTIVE = 'all_active'
MODE_NOT_CHECKED_7_DAYS = 'not_checked_7_days'
MODE_WATCH_SICK_CRITICAL = 'watch_sick_critical'
MODE_BY_LOCATION = 'by_location_text'

_WATCH_SICK_CRITICAL_STATUSES = {
    Observation.STATUS_WATCH,
    Observation.STATUS_SICK,
    Observation.STATUS_CRITICAL,
}


def get_units_for_round_generation(generation_mode, location_filter=None):
    """
    Return a queryset/list of active TrackingUnits matching the given mode.
    """
    base_qs = TrackingUnit.objects.filter(is_active=True).select_related(
        'crop', 'accession', 'batch', 'position__bench__screen_house__site',
    ).order_by('unit_code')

    if generation_mode == MODE_ALL_ACTIVE:
        return list(base_qs)

    if generation_mode == MODE_NOT_CHECKED_7_DAYS:
        cutoff = timezone.now() - timedelta(days=7)
        # Get unit PKs with a recent observation
        recent_pks = set(
            Observation.objects
            .filter(created_at__gte=cutoff)
            .values_list('tracking_unit_id', flat=True)
        )
        return [u for u in base_qs if u.pk not in recent_pks]

    if generation_mode == MODE_WATCH_SICK_CRITICAL:
        latest_status_subq = (
            Observation.objects
            .filter(tracking_unit=OuterRef('pk'))
            .order_by('-created_at')
            .values('status')[:1]
        )
        return list(
            base_qs
            .annotate(latest_status=Subquery(latest_status_subq))
            .filter(latest_status__in=list(_WATCH_SICK_CRITICAL_STATUSES))
        )

    if generation_mode == MODE_BY_LOCATION:
        if not location_filter:
            return []
        loc = location_filter.strip()
        return list(
            base_qs.filter(
                Q(location_text__icontains=loc) |
                Q(position__bench__name__icontains=loc) |
                Q(position__bench__screen_house__name__icontains=loc) |
                Q(position__bench__screen_house__site__name__icontains=loc)
            )
        )

    return list(base_qs)


def create_daily_round_with_items(
    *,
    name,
    date,
    generation_mode,
    location_filter='',
    assigned_to=None,
    notes='',
    created_by=None,
):
    """
    Create a DailyRound and DailyRoundItems for all matched active units.
    Raises ValidationError if no units match.
    Returns the created DailyRound.
    """
    units = get_units_for_round_generation(generation_mode, location_filter=location_filter)

    if not units:
        raise ValidationError(
            'No active tracking units matched this round. '
            'Adjust the unit selection mode or location filter and try again.'
        )

    with transaction.atomic():
        daily_round = DailyRound.objects.create(
            name=name,
            date=date,
            assigned_to=assigned_to,
            location_filter=location_filter,
            notes=notes,
            created_by=created_by,
        )
        items = [
            DailyRoundItem(daily_round=daily_round, tracking_unit=unit)
            for unit in units
        ]
        DailyRoundItem.objects.bulk_create(items, ignore_conflicts=True)

    return daily_round


def mark_overdue_rounds_missed():
    """
    Bulk-set rounds whose date has passed and are still planned/in_progress to missed.
    Call lazily from list/detail views so no scheduled task is required.
    """
    yesterday = timezone.localdate() - timedelta(days=1)
    DailyRound.objects.filter(
        date__lte=yesterday,
        status__in=[DailyRound.STATUS_PLANNED, DailyRound.STATUS_IN_PROGRESS],
    ).update(status=DailyRound.STATUS_MISSED)


def update_daily_round_status(daily_round):
    """
    Update DailyRound.status based on item completion state.

    - all completed → completed
    - at least one completed but not all → in_progress
    - none completed → planned (if currently planned or in_progress)

    Missed / cancelled are not changed automatically.
    """
    if daily_round.status in (DailyRound.STATUS_MISSED, DailyRound.STATUS_CANCELLED):
        return

    total = daily_round.items.count()
    completed = daily_round.items.filter(completed=True).count()

    if total == 0:
        return

    if completed == total:
        new_status = DailyRound.STATUS_COMPLETED
    elif completed > 0:
        new_status = DailyRound.STATUS_IN_PROGRESS
    else:
        new_status = DailyRound.STATUS_PLANNED

    if daily_round.status != new_status:
        DailyRound.objects.filter(pk=daily_round.pk).update(status=new_status)
        daily_round.status = new_status
