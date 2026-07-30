from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import (
    Accession, Batch, Bench, Crop, MovementHistory, Position, ScreenHouse, Site, TrackingUnit,
)
from inventory.services import get_accession_survival_stats, get_batch_survival_stats, record_movement
from monitoring.models import QuantityEvent
from monitoring.services import apply_quantity_event


def make_unit(unit_code='TU-SVC-MOVE-001', **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
        location_text='Bay A',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


def make_position(code='P1'):
    site = Site.objects.create(name=f'Site for {code}')
    sh = ScreenHouse.objects.create(site=site, name='SH1')
    bench = Bench.objects.create(screen_house=sh, name='Bench A')
    return Position.objects.create(bench=bench, code=code)


class RecordMovementServiceTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='move-service-user',
            password='test-password-123',
        )

    def test_move_to_structured_position_updates_unit(self):
        unit = make_unit('TU-SVC-MOVE-002')
        position = make_position('P2')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)

        unit.refresh_from_db()
        self.assertEqual(unit.position_id, position.pk)

    def test_move_to_structured_position_clears_nothing_unexpected(self):
        unit = make_unit('TU-SVC-MOVE-003', location_text='Old Bay')
        position = make_position('P3')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)

        unit.refresh_from_db()
        self.assertEqual(unit.position_id, position.pk)

    def test_move_to_free_text_location_clears_structured_position(self):
        position = make_position('P4')
        unit = make_unit('TU-SVC-MOVE-004', position=position)

        record_movement(tracking_unit=unit, to_location_text='New Bay', user=self.user)

        unit.refresh_from_db()
        self.assertIsNone(unit.position_id)
        self.assertEqual(unit.location_text, 'New Bay')

    def test_creates_movement_history_record_with_before_and_after(self):
        unit = make_unit('TU-SVC-MOVE-005', location_text='Bay A')
        position = make_position('P5')

        movement = record_movement(
            tracking_unit=unit, to_position=position, user=self.user, reason='Better light'
        )

        self.assertEqual(movement.from_location_text, 'Bay A')
        self.assertEqual(movement.to_position, position)
        self.assertEqual(movement.reason, 'Better light')
        self.assertEqual(MovementHistory.objects.filter(tracking_unit=unit).count(), 1)

    def test_requires_destination(self):
        unit = make_unit('TU-SVC-MOVE-006')

        with self.assertRaises(ValidationError):
            record_movement(tracking_unit=unit, user=self.user)

    def test_requires_tracking_unit(self):
        with self.assertRaises(ValidationError):
            record_movement(to_location_text='Bay Z', user=self.user)

    def test_second_move_captures_previous_destination_as_new_origin(self):
        unit = make_unit('TU-SVC-MOVE-007', location_text='Bay A')
        position = make_position('P7')

        record_movement(tracking_unit=unit, to_position=position, user=self.user)
        second_movement = record_movement(
            tracking_unit=unit, to_location_text='Bay C', user=self.user
        )

        self.assertEqual(second_movement.from_position, position)


# ── Survival analytics ─────────────────────────────────────────────────────────

def make_batch_with_units(batch_code='B1', crop_name='Crop A', accession_code='ACC-1',
                           initial_quantity=20, unit_quantities=(20,)):
    crop = Crop.objects.create(name=crop_name)
    accession = Accession.objects.create(crop=crop, accession_code=accession_code)
    batch = Batch.objects.create(accession=accession, batch_code=batch_code, initial_quantity=initial_quantity)
    units = []
    for i, qty in enumerate(unit_quantities, start=1):
        unit = TrackingUnit.objects.create(
            unit_code=f'TU-{batch_code}-{i}',
            unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name=crop_name,
            crop=crop,
            accession=accession,
            batch=batch,
            quantity=qty,
        )
        units.append(unit)
    return batch, units


class SurvivalStatsServiceTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='survival-service-user',
            password='test-password-123',
        )

    def _stats_for(self, batch):
        return next(row for row in get_batch_survival_stats() if row['batch'].pk == batch.pk)

    def test_full_survival_when_no_losses(self):
        batch, units = make_batch_with_units('B-FULL', initial_quantity=20, unit_quantities=(20,))

        row = self._stats_for(batch)

        self.assertEqual(row['current_quantity'], 20)
        self.assertEqual(row['lost_quantity'], 0)
        self.assertEqual(row['survival_rate'], 100.0)

    def test_survival_rate_reflects_deaths(self):
        batch, units = make_batch_with_units('B-DEATH', initial_quantity=20, unit_quantities=(20,))
        apply_quantity_event(
            tracking_unit=units[0], event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-5, user=self.user,
        )

        row = self._stats_for(batch)

        self.assertEqual(row['current_quantity'], 15)
        self.assertEqual(row['lost_quantity'], 5)
        self.assertEqual(row['survival_rate'], 75.0)

    def test_recount_is_not_counted_as_loss(self):
        batch, units = make_batch_with_units('B-RECOUNT', initial_quantity=20, unit_quantities=(20,))
        apply_quantity_event(
            tracking_unit=units[0], event_type=QuantityEvent.EVENT_TYPE_RECOUNT,
            quantity_change=-3, user=self.user,
        )

        row = self._stats_for(batch)

        self.assertEqual(row['current_quantity'], 17)
        self.assertEqual(row['lost_quantity'], 0)

    def test_survival_rate_none_when_no_initial_quantity(self):
        batch, units = make_batch_with_units('B-NOINIT', initial_quantity=0, unit_quantities=(5,))

        row = self._stats_for(batch)

        self.assertIsNone(row['survival_rate'])

    def test_inactive_batch_excluded(self):
        batch, units = make_batch_with_units('B-INACTIVE', initial_quantity=10, unit_quantities=(10,))
        batch.is_active = False
        batch.save()

        pks = [row['batch'].pk for row in get_batch_survival_stats()]

        self.assertNotIn(batch.pk, pks)

    def test_accession_stats_aggregate_across_batches(self):
        crop = Crop.objects.create(name='Aggregate Crop')
        accession = Accession.objects.create(crop=crop, accession_code='AGG-ACC-1')
        batch1 = Batch.objects.create(accession=accession, batch_code='AGG-B1', initial_quantity=10)
        batch2 = Batch.objects.create(accession=accession, batch_code='AGG-B2', initial_quantity=10)
        unit1 = TrackingUnit.objects.create(
            unit_code='TU-AGG-1', unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Aggregate Crop', crop=crop, accession=accession, batch=batch1, quantity=10,
        )
        unit2 = TrackingUnit.objects.create(
            unit_code='TU-AGG-2', unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
            crop_name='Aggregate Crop', crop=crop, accession=accession, batch=batch2, quantity=10,
        )
        apply_quantity_event(
            tracking_unit=unit1, event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-4, user=self.user,
        )

        row = next(r for r in get_accession_survival_stats() if r['accession'].pk == accession.pk)

        self.assertEqual(row['initial_quantity'], 20)
        self.assertEqual(row['current_quantity'], 16)
        self.assertEqual(row['lost_quantity'], 4)
        self.assertEqual(row['survival_rate'], 80.0)
