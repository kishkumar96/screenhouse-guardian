from datetime import datetime, time as dt_time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone

from inventory.models import TrackingUnit

from .models import (
    DailyRound, DailyRoundItem, DistributionEvent, EnvironmentalLog, Observation, PropagationEvent,
    QuantityEvent, Treatment,
)


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


# ── Weekly report ──────────────────────────────────────────────────────────────

_LOSS_EVENT_TYPES = [QuantityEvent.EVENT_TYPE_DEATH, QuantityEvent.EVENT_TYPE_LOSS]

_RESOLVED_TREATMENT_OUTCOMES = [
    Treatment.OUTCOME_IMPROVED,
    Treatment.OUTCOME_NO_CHANGE,
    Treatment.OUTCOME_WORSENED,
    Treatment.OUTCOME_RESOLVED,
]


def get_weekly_summary(end_date=None):
    """
    Summarise field activity for the 7-day period ending on end_date (inclusive).

    end_date defaults to today. Returns a dict of counts used to render the
    weekly report: observations by status, round completion, treatments
    applied, follow-ups resolved/still overdue, quantity losses, and
    tracking unit churn (created/archived).
    """
    if end_date is None:
        end_date = timezone.localdate()
    start_date = end_date - timedelta(days=6)

    start_dt = timezone.make_aware(datetime.combine(start_date, dt_time.min))
    end_dt = timezone.make_aware(datetime.combine(end_date, dt_time.max))

    observations = Observation.objects.filter(created_at__range=(start_dt, end_dt))
    observation_status_breakdown = [
        (label, observations.filter(status=value).count())
        for value, label in Observation.STATUS_CHOICES
    ]

    rounds_in_period = DailyRound.objects.filter(date__range=(start_date, end_date))
    round_status_breakdown = [
        (label, rounds_in_period.filter(status=value).count())
        for value, label in DailyRound.STATUS_CHOICES
    ]
    round_items_in_period = DailyRoundItem.objects.filter(daily_round__in=rounds_in_period)
    round_items_total = round_items_in_period.count()
    round_items_completed = round_items_in_period.filter(completed=True).count()

    treatments_in_period = Treatment.objects.filter(treatment_date__range=(start_dt, end_dt))
    _treatment_type_labels = dict(Treatment.TYPE_CHOICES)
    treatment_type_breakdown = [
        (_treatment_type_labels.get(row['treatment_type'], row['treatment_type']), row['count'])
        for row in (
            treatments_in_period
            .values('treatment_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
    ]

    follow_ups_resolved = Treatment.objects.filter(
        outcome__in=_RESOLVED_TREATMENT_OUTCOMES,
        updated_at__range=(start_dt, end_dt),
    ).count()
    follow_ups_still_overdue = Treatment.objects.filter(
        outcome=Treatment.OUTCOME_PENDING,
        follow_up_date__isnull=False,
        follow_up_date__lt=end_date,
    ).count()

    quantity_events_in_period = QuantityEvent.objects.filter(event_date__range=(start_dt, end_dt))
    lost_changes = quantity_events_in_period.filter(
        event_type__in=_LOSS_EVENT_TYPES
    ).values_list('quantity_change', flat=True)
    quantity_lost_total = -sum(lost_changes)

    new_units = TrackingUnit.objects.filter(created_at__range=(start_dt, end_dt)).count()
    archived_units = TrackingUnit.objects.filter(archived_at__range=(start_dt, end_dt)).count()

    return {
        'start_date': start_date,
        'end_date': end_date,
        'observation_total': observations.count(),
        'observation_status_breakdown': observation_status_breakdown,
        'round_status_breakdown': round_status_breakdown,
        'round_items_total': round_items_total,
        'round_items_completed': round_items_completed,
        'treatment_total': treatments_in_period.count(),
        'treatment_type_breakdown': treatment_type_breakdown,
        'follow_ups_resolved': follow_ups_resolved,
        'follow_ups_still_overdue': follow_ups_still_overdue,
        'quantity_event_total': quantity_events_in_period.count(),
        'quantity_lost_total': quantity_lost_total,
        'new_units': new_units,
        'archived_units': archived_units,
    }


# ── Distribution events ─────────────────────────────────────────────────────────

def record_distribution(
    *,
    tracking_unit=None,
    tracking_unit_id=None,
    quantity,
    recipient_name,
    recipient_organisation='',
    purpose='',
    notes='',
    user,
):
    """
    Record that quantity was distributed to an external recipient.

    Reduces the tracking unit's quantity through the existing quantity-event
    service (as a LOSS event, so the change is auditable alongside deaths and
    other losses) and creates an immutable DistributionEvent recording who
    received it and why, atomically.
    """
    if tracking_unit is None and tracking_unit_id is None:
        raise ValidationError('tracking_unit or tracking_unit_id is required.')

    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError({'quantity': 'quantity must be a positive integer.'})

    if not recipient_name:
        raise ValidationError({'recipient_name': 'recipient_name is required.'})

    if tracking_unit is not None:
        tracking_unit_id = tracking_unit.pk

    with transaction.atomic():
        unit = TrackingUnit.objects.select_for_update().get(pk=tracking_unit_id)

        reason = f'Distributed to {recipient_name}'
        if recipient_organisation:
            reason += f' ({recipient_organisation})'

        apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_LOSS,
            quantity_change=-quantity,
            user=user,
            reason=reason,
        )

        event = DistributionEvent(
            tracking_unit=unit,
            quantity=quantity,
            recipient_name=recipient_name,
            recipient_organisation=recipient_organisation,
            purpose=purpose,
            notes=notes,
            created_by=user,
        )
        event.full_clean()
        event.save()

        return event


# ── Propagation events ──────────────────────────────────────────────────────────

def record_propagation(
    *,
    parent_unit=None,
    parent_unit_id=None,
    method,
    quantity_taken=None,
    notes='',
    user,
    resulting_units=None,
):
    """
    Record that new tracking units were propagated from a parent unit.

    If quantity_taken is given, it is deducted from the parent unit's
    quantity through the existing quantity-event service (as a LOSS event,
    reason noting propagation), since that material left the source unit.
    resulting_units (an iterable of already-created TrackingUnit rows) are
    linked to the event via its M2M field; new units are still created the
    normal way (e.g. admin) — this only records the link and any material
    taken from the parent.
    """
    if parent_unit is None and parent_unit_id is None:
        raise ValidationError('parent_unit or parent_unit_id is required.')

    if parent_unit is not None:
        parent_unit_id = parent_unit.pk

    with transaction.atomic():
        unit = TrackingUnit.objects.select_for_update().get(pk=parent_unit_id)

        if quantity_taken:
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_LOSS,
                quantity_change=-quantity_taken,
                user=user,
                reason=f'Propagation ({dict(PropagationEvent.METHOD_CHOICES).get(method, method)})',
            )

        event = PropagationEvent(
            parent_unit=unit,
            method=method,
            quantity_taken=quantity_taken,
            notes=notes,
            created_by=user,
        )
        event.full_clean()
        event.save()

        if resulting_units:
            event.resulting_units.set(resulting_units)

        return event


# ── Environmental logs ────────────────────────────────────────────────────────────

def record_environmental_log(
    *,
    position=None,
    position_id=None,
    temperature_c=None,
    humidity_pct=None,
    light_lux=None,
    notes='',
    user,
):
    """
    Record an environmental reading (temperature/humidity/light) for a position.

    At least one of temperature_c, humidity_pct, or light_lux must be given —
    a sensor station may not report all three. Creates an immutable
    EnvironmentalLog.
    """
    if temperature_c is None and humidity_pct is None and light_lux is None:
        raise ValidationError(
            'At least one of temperature_c, humidity_pct, or light_lux is required.'
        )

    if position is not None:
        position_id = position.pk

    log = EnvironmentalLog(
        position_id=position_id,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        light_lux=light_lux,
        notes=notes,
        recorded_by=user,
    )
    log.full_clean()
    log.save()
    return log
