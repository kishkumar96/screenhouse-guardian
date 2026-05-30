from datetime import timedelta

from django.db.models import Prefetch
from django.utils import timezone

from inventory.models import TrackingUnit
from monitoring.models import DailyRound, DailyRoundItem, Observation, Treatment


def get_latest_observation_for_unit(unit):
    """Return the latest Observation for a unit by created_at, or None."""
    return unit.observations.order_by('-created_at').first()


def get_dashboard_data():
    """Return summary stats and active unit list for the Phase 1A dashboard."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)

    units = list(
        TrackingUnit.objects.filter(is_active=True)
        .select_related(
            'crop',
            'accession',
            'batch',
            'position__bench__screen_house__site',
        )
        .prefetch_related(
            Prefetch(
                'observations',
                queryset=Observation.objects.order_by('-created_at'),
                to_attr='prefetched_observations',
            )
        )
        .order_by('unit_code')
    )

    for unit in units:
        unit.latest_observation = (
            unit.prefetched_observations[0]
            if unit.prefetched_observations
            else None
        )

    total_units = len(units)
    total_quantity = sum(u.quantity for u in units)
    units_with_qr = sum(1 for u in units if u.qr_code)
    units_without_qr = total_units - units_with_qr
    units_checked_today = sum(
        1 for u in units
        if u.latest_observation and u.latest_observation.created_at >= today_start
    )
    units_not_checked_7_days = sum(
        1 for u in units
        if not u.latest_observation or u.latest_observation.created_at < seven_days_ago
    )

    today = timezone.localdate()

    pending_followups = (
        Treatment.objects
        .filter(follow_up_date__isnull=False, outcome=Treatment.OUTCOME_PENDING)
        .count()
    )
    overdue_followups = (
        Treatment.objects
        .filter(
            follow_up_date__isnull=False,
            follow_up_date__lte=today,
            outcome=Treatment.OUTCOME_PENDING,
        )
        .count()
    )
    overdue_followup_list = list(
        Treatment.objects
        .filter(
            follow_up_date__isnull=False,
            follow_up_date__lte=today,
            outcome=Treatment.OUTCOME_PENDING,
        )
        .select_related('tracking_unit', 'created_by')
        .order_by('follow_up_date')[:5]
    )

    # Daily round summary for today
    rounds_today = DailyRound.objects.filter(date=today).order_by('name')
    round_items_today = DailyRoundItem.objects.filter(daily_round__date=today)
    rounds_today_count = rounds_today.count()
    round_items_completed_today = round_items_today.filter(completed=True).count()
    round_items_pending_today = round_items_today.filter(completed=False).count()
    rounds_today_list = list(
        rounds_today.select_related('assigned_to').prefetch_related('items')[:5]
    )

    return {
        'units': units,
        'total_units': total_units,
        'total_quantity': total_quantity,
        'units_with_qr': units_with_qr,
        'units_without_qr': units_without_qr,
        'units_checked_today': units_checked_today,
        'units_not_checked_7_days': units_not_checked_7_days,
        'pending_followups': pending_followups,
        'overdue_followups': overdue_followups,
        'overdue_followup_list': overdue_followup_list,
        'rounds_today_count': rounds_today_count,
        'round_items_completed_today': round_items_completed_today,
        'round_items_pending_today': round_items_pending_today,
        'rounds_today_list': rounds_today_list,
    }
