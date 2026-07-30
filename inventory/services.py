from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import Batch, MovementHistory, TrackingUnit


def record_movement(
    *,
    tracking_unit=None,
    tracking_unit_id=None,
    to_position=None,
    to_location_text='',
    user,
    reason='',
):
    """
    Move a tracking unit to a new structured position or free-text location.

    Records an immutable MovementHistory entry capturing the unit's previous
    position/location, then updates the unit's current position/location_text
    atomically. Exactly one of to_position or to_location_text should be set;
    setting to_position clears the unit's free-text location (structured
    position takes display precedence), and setting to_location_text clears
    the unit's structured position.
    """
    if tracking_unit is None and tracking_unit_id is None:
        raise ValidationError('tracking_unit or tracking_unit_id is required.')

    if to_position is None and not to_location_text:
        raise ValidationError('Provide either to_position or to_location_text.')

    if tracking_unit is not None:
        if tracking_unit.pk is None:
            raise ValidationError('tracking_unit must be saved before recording a movement.')
        if tracking_unit_id is not None and tracking_unit_id != tracking_unit.pk:
            raise ValidationError('tracking_unit and tracking_unit_id must refer to the same row.')
        tracking_unit_id = tracking_unit.pk

    with transaction.atomic():
        unit = TrackingUnit.objects.select_for_update().get(pk=tracking_unit_id)

        movement = MovementHistory(
            tracking_unit=unit,
            from_position=unit.position,
            to_position=to_position,
            from_location_text=unit.location_text,
            to_location_text=to_location_text,
            reason=reason,
            moved_by=user,
        )
        movement.full_clean()
        movement.save()

        if to_position is not None:
            unit.position = to_position
            unit.save(update_fields=['position'])
        else:
            unit.position = None
            unit.location_text = to_location_text
            unit.save(update_fields=['position', 'location_text'])

        return movement


# ── Survival analytics ─────────────────────────────────────────────────────────

def get_batch_survival_stats():
    """
    For each active Batch, compare its recorded initial_quantity against the
    current total quantity across its tracking units and the cumulative
    death/loss quantity recorded against those units, to give a survival rate.

    Returns a list of dicts: batch, initial_quantity, current_quantity,
    lost_quantity, survival_rate (percentage, 1 decimal, or None if the batch
    has no recorded initial_quantity).
    """
    from monitoring.models import QuantityEvent  # avoid a module-level cross-app import cycle

    stats = []
    batches = (
        Batch.objects.filter(is_active=True)
        .select_related('accession__crop')
        .order_by('accession__crop__name', 'batch_code')
    )
    for batch in batches:
        current_quantity = batch.tracking_units.aggregate(total=Sum('quantity'))['total'] or 0
        lost = QuantityEvent.objects.filter(
            tracking_unit__batch=batch,
            event_type__in=[QuantityEvent.EVENT_TYPE_DEATH, QuantityEvent.EVENT_TYPE_LOSS],
        ).aggregate(total=Sum('quantity_change'))['total'] or 0
        lost_quantity = -lost

        initial_quantity = batch.initial_quantity
        survival_rate = (
            round((current_quantity / initial_quantity) * 100, 1) if initial_quantity else None
        )

        stats.append({
            'batch': batch,
            'initial_quantity': initial_quantity,
            'current_quantity': current_quantity,
            'lost_quantity': lost_quantity,
            'survival_rate': survival_rate,
        })
    return stats


def get_accession_survival_stats():
    """
    Aggregate get_batch_survival_stats() up to the Accession level.
    """
    by_accession = {}
    for row in get_batch_survival_stats():
        accession = row['batch'].accession
        agg = by_accession.setdefault(accession.pk, {
            'accession': accession,
            'initial_quantity': 0,
            'current_quantity': 0,
            'lost_quantity': 0,
        })
        agg['initial_quantity'] += row['initial_quantity']
        agg['current_quantity'] += row['current_quantity']
        agg['lost_quantity'] += row['lost_quantity']

    results = list(by_accession.values())
    for row in results:
        row['survival_rate'] = (
            round((row['current_quantity'] / row['initial_quantity']) * 100, 1)
            if row['initial_quantity'] else None
        )
    results.sort(key=lambda r: (r['accession'].crop.name, r['accession'].accession_code))
    return results
