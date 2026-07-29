from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MovementHistory, TrackingUnit


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
