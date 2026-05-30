from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import TrackingUnit
import datetime

from monitoring.models import DailyRound, DailyRoundItem, Observation, QuantityEvent
from monitoring.services import (
    apply_quantity_event,
    create_daily_round_with_items,
    get_units_for_round_generation,
    update_daily_round_status,
    MODE_ALL_ACTIVE,
    MODE_NOT_CHECKED_7_DAYS,
    MODE_WATCH_SICK_CRITICAL,
    MODE_BY_LOCATION,
)


def make_container(unit_code='TU-SVC-001', quantity=10):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=quantity,
    )


class ApplyQuantityEventServiceTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='service-user',
            password='test-password-123',
        )

    def test_death_event_decreases_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-DEATH-001', quantity=50)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-4,
            user=self.user,
            reason='Routine culling.',
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 46)
        self.assertEqual(event.quantity_before, 50)
        self.assertEqual(event.quantity_change, -4)
        self.assertEqual(event.quantity_after, 46)

    def test_loss_event_decreases_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-LOSS-001', quantity=12)

        apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_LOSS,
            quantity_change=-2,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 10)

    def test_correction_event_can_increase_tracking_unit_quantity(self):
        unit = make_container('TU-SVC-CORR-001', quantity=8)

        apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=3,
            user=self.user,
            reason='Recount found additional seedlings.',
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 11)

    def test_negative_result_raises_validation_error(self):
        unit = make_container('TU-SVC-NEG-001', quantity=3)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_DEATH,
                quantity_change=-5,
                user=self.user,
            )

        self.assertIn('quantity_change', ctx.exception.message_dict)

    def test_negative_result_creates_no_event_and_leaves_quantity_unchanged(self):
        unit = make_container('TU-SVC-NEG-002', quantity=3)

        with self.assertRaises(ValidationError):
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_LOSS,
                quantity_change=-10,
                user=self.user,
            )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 3)
        self.assertEqual(QuantityEvent.objects.filter(tracking_unit=unit).count(), 0)

    def test_created_event_has_expected_fields(self):
        unit = make_container('TU-SVC-FIELDS-001', quantity=20)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_LOSS,
            quantity_change=-6,
            user=self.user,
            reason='Storm damage.',
        )

        self.assertEqual(event.quantity_before, 20)
        self.assertEqual(event.quantity_change, -6)
        self.assertEqual(event.quantity_after, 14)
        self.assertEqual(event.event_type, QuantityEvent.EVENT_TYPE_LOSS)
        self.assertEqual(event.reason, 'Storm damage.')
        self.assertEqual(event.created_by, self.user)

    def test_service_returns_created_quantity_event(self):
        unit = make_container('TU-SVC-RETURN-001', quantity=7)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=1,
            user=self.user,
        )

        self.assertIsInstance(event, QuantityEvent)
        self.assertIsNotNone(event.pk)

    def test_service_works_with_tracking_unit_id(self):
        unit = make_container('TU-SVC-ID-001', quantity=15)

        event = apply_quantity_event(
            tracking_unit_id=unit.pk,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-5,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 10)
        self.assertEqual(event.tracking_unit_id, unit.pk)

    def test_service_works_with_tracking_unit_instance(self):
        unit = make_container('TU-SVC-INSTANCE-001', quantity=9)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=2,
            user=self.user,
        )

        unit.refresh_from_db()
        self.assertEqual(unit.quantity, 11)
        self.assertEqual(event.tracking_unit, unit)

    def test_invalid_event_type_raises_validation_error(self):
        unit = make_container('TU-SVC-TYPE-001', quantity=9)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type='bad_type',
                quantity_change=-1,
                user=self.user,
            )

        self.assertIn('event_type', ctx.exception.message_dict)

    def test_non_integer_quantity_change_raises_validation_error(self):
        unit = make_container('TU-SVC-INT-001', quantity=9)

        with self.assertRaises(ValidationError) as ctx:
            apply_quantity_event(
                tracking_unit=unit,
                event_type=QuantityEvent.EVENT_TYPE_DEATH,
                quantity_change='-1',
                user=self.user,
            )

        self.assertIn('quantity_change', ctx.exception.message_dict)

    def test_service_allows_user_none(self):
        unit = make_container('TU-SVC-USER-001', quantity=5)

        event = apply_quantity_event(
            tracking_unit=unit,
            event_type=QuantityEvent.EVENT_TYPE_CORRECTION,
            quantity_change=1,
            user=None,
        )

        self.assertIsNone(event.created_by)


# ── Daily round service tests ─────────────────────────────────────────────────

def make_active_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=5,
        location_text='Bay 1',
        is_active=True,
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


def make_observation(unit, status=Observation.STATUS_HEALTHY, days_ago=0):
    from django.utils import timezone
    obs = Observation.objects.create(
        tracking_unit=unit,
        observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
        status=status,
    )
    if days_ago:
        Observation.objects.filter(pk=obs.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=days_ago)
        )
    return obs


class GetUnitsForRoundGenerationTest(TestCase):

    def test_all_active_includes_active_units(self):
        u = make_active_unit('TU-GEN-001')
        units = get_units_for_round_generation(MODE_ALL_ACTIVE)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_all_active_excludes_inactive_units(self):
        make_active_unit('TU-GEN-ARCH', is_active=False)
        units = get_units_for_round_generation(MODE_ALL_ACTIVE)
        for u in units:
            self.assertTrue(u.is_active)

    def test_not_checked_7_days_includes_units_with_no_observations(self):
        u = make_active_unit('TU-GEN-NOCH')
        units = get_units_for_round_generation(MODE_NOT_CHECKED_7_DAYS)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_not_checked_7_days_includes_units_checked_more_than_7_days_ago(self):
        u = make_active_unit('TU-GEN-OLD')
        make_observation(u, days_ago=8)
        units = get_units_for_round_generation(MODE_NOT_CHECKED_7_DAYS)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_not_checked_7_days_excludes_recently_checked_units(self):
        u = make_active_unit('TU-GEN-RECENT')
        make_observation(u, days_ago=1)
        units = get_units_for_round_generation(MODE_NOT_CHECKED_7_DAYS)
        pks = [x.pk for x in units]
        self.assertNotIn(u.pk, pks)

    def test_watch_sick_critical_includes_watch_units(self):
        u = make_active_unit('TU-GEN-WATCH')
        make_observation(u, status=Observation.STATUS_WATCH)
        units = get_units_for_round_generation(MODE_WATCH_SICK_CRITICAL)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_watch_sick_critical_includes_sick_units(self):
        u = make_active_unit('TU-GEN-SICK')
        make_observation(u, status=Observation.STATUS_SICK)
        units = get_units_for_round_generation(MODE_WATCH_SICK_CRITICAL)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_watch_sick_critical_includes_critical_units(self):
        u = make_active_unit('TU-GEN-CRIT')
        make_observation(u, status=Observation.STATUS_CRITICAL)
        units = get_units_for_round_generation(MODE_WATCH_SICK_CRITICAL)
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)

    def test_watch_sick_critical_excludes_healthy_units(self):
        u = make_active_unit('TU-GEN-HEALTH')
        make_observation(u, status=Observation.STATUS_HEALTHY)
        units = get_units_for_round_generation(MODE_WATCH_SICK_CRITICAL)
        pks = [x.pk for x in units]
        self.assertNotIn(u.pk, pks)

    def test_by_location_text_filters_matching_location(self):
        u = make_active_unit('TU-GEN-BAY3', location_text='Bay 3')
        make_active_unit('TU-GEN-BAY7', location_text='Bay 7')
        units = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='Bay 3')
        pks = [x.pk for x in units]
        self.assertIn(u.pk, pks)
        self.assertEqual(len(pks), 1)

    def test_by_location_text_with_empty_filter_returns_empty(self):
        make_active_unit('TU-GEN-LOC-EMPTY')
        units = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='')
        self.assertEqual(units, [])


class CreateDailyRoundWithItemsTest(TestCase):

    def test_creates_expected_number_of_items(self):
        make_active_unit('TU-CRI-001')
        make_active_unit('TU-CRI-002')
        make_active_unit('TU-CRI-003', is_active=False)
        dr = create_daily_round_with_items(
            name='Test round',
            date=datetime.date.today(),
            generation_mode=MODE_ALL_ACTIVE,
        )
        self.assertEqual(dr.items.count(), 2)

    def test_rejects_zero_matched_units(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            create_daily_round_with_items(
                name='Empty round',
                date=datetime.date.today(),
                generation_mode=MODE_ALL_ACTIVE,
            )


class UpdateDailyRoundStatusTest(TestCase):

    def setUp(self):
        self.unit1 = make_active_unit('TU-UPD-001')
        self.unit2 = make_active_unit('TU-UPD-002')
        self.dr = DailyRound.objects.create(name='Status test', date=datetime.date.today())
        self.item1 = DailyRoundItem.objects.create(daily_round=self.dr, tracking_unit=self.unit1)
        self.item2 = DailyRoundItem.objects.create(daily_round=self.dr, tracking_unit=self.unit2)

    def test_completing_one_item_sets_in_progress(self):
        DailyRoundItem.objects.filter(pk=self.item1.pk).update(completed=True)
        self.dr.refresh_from_db()
        update_daily_round_status(self.dr)
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_IN_PROGRESS)

    def test_completing_all_items_sets_completed(self):
        DailyRoundItem.objects.filter(daily_round=self.dr).update(completed=True)
        self.dr.refresh_from_db()
        update_daily_round_status(self.dr)
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_COMPLETED)

    def test_no_items_completed_leaves_planned(self):
        update_daily_round_status(self.dr)
        self.dr.refresh_from_db()
        self.assertEqual(self.dr.status, DailyRound.STATUS_PLANNED)


# ── Fix 2: watch_sick_critical uses single annotated query ────────────────────

class WatchSickCriticalQueryTest(TestCase):

    def test_watch_sick_critical_uses_annotation_not_loop(self):
        """Verify correct results with multiple units — catches annotation bugs."""
        healthy = make_active_unit('TU-WSC-H')
        sick = make_active_unit('TU-WSC-S')
        watch = make_active_unit('TU-WSC-W')
        no_obs = make_active_unit('TU-WSC-N')

        make_observation(healthy, status=Observation.STATUS_HEALTHY)
        make_observation(sick, status=Observation.STATUS_SICK)
        make_observation(watch, status=Observation.STATUS_WATCH)

        units = get_units_for_round_generation(MODE_WATCH_SICK_CRITICAL)
        pks = {u.pk for u in units}
        self.assertIn(sick.pk, pks)
        self.assertIn(watch.pk, pks)
        self.assertNotIn(healthy.pk, pks)
        self.assertNotIn(no_obs.pk, pks)


# ── Fix 4: location filter uses ORM Q ────────────────────────────────────────

class LocationFilterQFilterTest(TestCase):

    def test_by_location_matches_location_text(self):
        u = make_active_unit('TU-LOC-TXT', location_text='Bay 5 North')
        units = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='Bay 5')
        self.assertIn(u.pk, [x.pk for x in units])

    def test_by_location_excludes_non_matching(self):
        make_active_unit('TU-LOC-NO', location_text='Section A')
        units = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='Bay 5')
        self.assertNotIn('TU-LOC-NO', [x.unit_code for x in units])

    def test_by_location_case_insensitive(self):
        u = make_active_unit('TU-LOC-CASE', location_text='bay 3')
        units = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='BAY 3')
        self.assertIn(u.pk, [x.pk for x in units])

    def test_by_location_empty_filter_returns_empty(self):
        make_active_unit('TU-LOC-EMP2', location_text='Bay 1')
        result = get_units_for_round_generation(MODE_BY_LOCATION, location_filter='')
        self.assertEqual(result, [])


# ── Fix 3: mark_overdue_rounds_missed ────────────────────────────────────────

class MarkOverdueRoundsMissedTest(TestCase):

    def test_past_planned_round_becomes_missed(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        dr = DailyRound.objects.create(name='Old round', date=yesterday)
        from monitoring.services import mark_overdue_rounds_missed
        mark_overdue_rounds_missed()
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_MISSED)

    def test_past_in_progress_round_becomes_missed(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        dr = DailyRound.objects.create(
            name='Partial round', date=yesterday, status=DailyRound.STATUS_IN_PROGRESS
        )
        from monitoring.services import mark_overdue_rounds_missed
        mark_overdue_rounds_missed()
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_MISSED)

    def test_todays_round_is_not_marked_missed(self):
        today = datetime.date.today()
        dr = DailyRound.objects.create(name='Today round', date=today)
        from monitoring.services import mark_overdue_rounds_missed
        mark_overdue_rounds_missed()
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_PLANNED)

    def test_completed_round_is_not_changed(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        dr = DailyRound.objects.create(
            name='Done round', date=yesterday, status=DailyRound.STATUS_COMPLETED
        )
        from monitoring.services import mark_overdue_rounds_missed
        mark_overdue_rounds_missed()
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_COMPLETED)

    def test_cancelled_round_is_not_changed(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        dr = DailyRound.objects.create(
            name='Cancelled round', date=yesterday, status=DailyRound.STATUS_CANCELLED
        )
        from monitoring.services import mark_overdue_rounds_missed
        mark_overdue_rounds_missed()
        dr.refresh_from_db()
        self.assertEqual(dr.status, DailyRound.STATUS_CANCELLED)
