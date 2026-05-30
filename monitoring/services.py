from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import TrackingUnit

from .models import QuantityEvent


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
