from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from inventory.models import (
    Accession, Bench, Crop, Position, ScreenHouse, Site, TrackingUnit,
)
import datetime

from monitoring.models import Observation, Treatment

User = get_user_model()

_PASSWORD = 'testpass123'


def make_observer(username='dash_observer'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Observer')
    user.groups.add(group)
    return user


def make_manager(username='dash_manager'):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    group, _ = Group.objects.get_or_create(name='Manager')
    user.groups.add(group)
    return user


def make_unit(unit_code, **kwargs):
    defaults = dict(
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=10,
        location_text='Bay 1',
    )
    defaults.update(kwargs)
    return TrackingUnit.objects.create(unit_code=unit_code, **defaults)


def make_observation(unit, **kwargs):
    defaults = dict(
        tracking_unit=unit,
        observation_type=Observation.OBSERVATION_TYPE_ROUTINE,
        status=Observation.STATUS_HEALTHY,
    )
    defaults.update(kwargs)
    return Observation.objects.create(**defaults)


class DashboardIndexTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='dash_observer', password=_PASSWORD)

    def test_index_returns_200(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_shows_total_active_unit_count(self):
        make_unit('TU-D-001')
        make_unit('TU-D-002')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['total_units'], 2)

    def test_active_unit_appears_in_table(self):
        unit = make_unit('TU-ACTIVE-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, unit.unit_code)

    def test_inactive_unit_excluded_from_table(self):
        active = make_unit('TU-ACT-001')
        inactive = make_unit('TU-INACT-001', is_active=False)
        response = self.client.get('/dashboard/')
        self.assertContains(response, active.unit_code)
        self.assertNotContains(response, inactive.unit_code)

    def test_shows_unit_code_in_table(self):
        make_unit('TU-CODE-TEST-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'TU-CODE-TEST-001')

    def test_shows_crop_name_in_table(self):
        make_unit('TU-CROP-001', crop_name='Baobab Tree')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Baobab Tree')

    def test_shows_quantity_in_table(self):
        make_unit('TU-QTY-001', quantity=55)
        response = self.client.get('/dashboard/')
        self.assertContains(response, '55')

    def test_shows_location_text_in_table(self):
        make_unit('TU-LOC-001', location_text='Bay 7 North')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Bay 7 North')

    def test_shows_latest_observation_status_when_present(self):
        unit = make_unit('TU-STATUS-001')
        make_observation(unit, status=Observation.STATUS_SICK)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Sick')

    def test_shows_not_checked_when_no_observation(self):
        make_unit('TU-NOOBS-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Not checked')

    def test_includes_qr_label_link(self):
        unit = make_unit('TU-QRL-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/qr/units/{unit.unit_code}/label/')

    def test_includes_observe_link(self):
        unit = make_unit('TU-OBS-LNK-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/observe/{unit.unit_code}/')

    def test_includes_timeline_link(self):
        unit = make_unit('TU-TL-LNK-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/observe/{unit.unit_code}/timeline/')

    def test_counts_units_with_and_without_qr(self):
        make_unit('TU-NQRC-001')
        make_unit('TU-NQRC-002')
        qr_unit = make_unit('TU-YQRC-001')
        TrackingUnit.objects.filter(pk=qr_unit.pk).update(qr_code='qr_codes/test.png')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['units_with_qr'], 1)
        self.assertEqual(response.context['units_without_qr'], 2)

    def test_counts_units_checked_today(self):
        checked = make_unit('TU-TODAY-001')
        make_unit('TU-UNTODAY-001')
        make_observation(checked, status=Observation.STATUS_HEALTHY)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.context['units_checked_today'], 1)


class DashboardManagerLinksTest(TestCase):

    def test_observer_does_not_see_export_link(self):
        make_observer('dash_obs_noexp')
        self.client.login(username='dash_obs_noexp', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['show_manager_links'])
        self.assertNotContains(response, 'Export data')

    def test_manager_sees_export_link(self):
        make_manager()
        self.client.login(username='dash_manager', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['show_manager_links'])
        self.assertContains(response, 'Export data')

    def test_manager_sees_generate_qr_for_unit_without_qr(self):
        make_manager()
        self.client.login(username='dash_manager', password=_PASSWORD)
        make_unit('TU-NOQR-MGR-001')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Generate QR')
        self.assertContains(response, 'name="next" value="/dashboard/"', html=False)

    def test_observer_does_not_see_generate_qr_button(self):
        make_observer('dash_obs_noqr')
        self.client.login(username='dash_obs_noqr', password=_PASSWORD)
        make_unit('TU-NOQR-OBS-001')
        response = self.client.get('/dashboard/')
        self.assertNotContains(response, 'Generate QR')

    def test_manager_does_not_see_generate_qr_for_unit_with_qr(self):
        make_manager()
        self.client.login(username='dash_manager', password=_PASSWORD)
        unit = make_unit('TU-HASQR-MGR-001')
        TrackingUnit.objects.filter(pk=unit.pk).update(qr_code='qr_codes/test.png')
        response = self.client.get('/dashboard/')
        self.assertNotContains(response, 'Generate QR')

    def test_staff_user_sees_create_unit_admin_link(self):
        user = User.objects.create_user(username='staff_dash', password=_PASSWORD, is_staff=True)
        group, _ = Group.objects.get_or_create(name='Manager')
        user.groups.add(group)
        self.client.login(username='staff_dash', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertTrue(response.context['show_staff_links'])
        self.assertContains(response, 'Create unit in admin')

    def test_non_staff_observer_does_not_see_admin_link(self):
        make_observer('dash_obs_nostaff')
        self.client.login(username='dash_obs_nostaff', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertFalse(response.context['show_staff_links'])
        self.assertNotContains(response, 'Create unit in admin')


# ── Phase 1B: display property fallback / structured tests ────────────────────

def _make_structured_position(site_name='Dash Site', sh_name='DSH1', bench_name='Bench X', pos_code='P1'):
    site, _ = Site.objects.get_or_create(name=site_name)
    sh, _ = ScreenHouse.objects.get_or_create(site=site, name=sh_name)
    bench, _ = Bench.objects.get_or_create(screen_house=sh, name=bench_name)
    pos, _ = Position.objects.get_or_create(bench=bench, code=pos_code)
    return pos


class DashboardDisplayPropertiesTest(TestCase):

    def setUp(self):
        self.user = make_observer('dash_disp_obs')
        self.client.login(username='dash_disp_obs', password=_PASSWORD)

    def test_shows_structured_crop_name_when_linked(self):
        crop = Crop.objects.create(name='Structured Cassava')
        make_unit('TU-DISP-001', crop_name='Old Cassava', crop=crop)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Structured Cassava')

    def test_falls_back_to_crop_name_when_no_crop_fk(self):
        make_unit('TU-DISP-002', crop_name='Fallback Crop')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Fallback Crop')

    def test_shows_structured_location_when_position_linked(self):
        pos = _make_structured_position(
            site_name='SiteDash', sh_name='SH99', bench_name='Bench Z', pos_code='PZ'
        )
        make_unit('TU-DISP-003', location_text='Old Location', position=pos)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'SiteDash / SH99 / Bench Z / PZ')

    def test_falls_back_to_location_text_when_no_position_fk(self):
        make_unit('TU-DISP-004', location_text='Fallback Bay 5')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Fallback Bay 5')

    def test_shows_structured_accession_when_linked(self):
        crop = Crop.objects.create(name='Crop For Acc')
        acc = Accession.objects.create(crop=crop, accession_code='STRUCT-ACC-001')
        make_unit('TU-DISP-005', crop_name='Crop For Acc', accession_code='OLD-ACC', accession=acc)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'STRUCT-ACC-001')

    def test_falls_back_to_accession_code_when_no_accession_fk(self):
        make_unit('TU-DISP-006', accession_code='LEGACY-ACC-006')
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'LEGACY-ACC-006')


# ── Dashboard Quantity action link ────────────────────────────────────────────

class DashboardQuantityLinkTest(TestCase):

    def setUp(self):
        self.unit = make_unit('TU-DASH-QTY-001')

    def test_manager_sees_quantity_link(self):
        make_manager('dash_qty_mgr')
        self.client.login(username='dash_qty_mgr', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertContains(response, f'/monitoring/units/{self.unit.unit_code}/quantity-event/')
        self.assertContains(response, 'Quantity')

    def test_observer_does_not_see_quantity_link(self):
        make_observer('dash_qty_obs')
        self.client.login(username='dash_qty_obs', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertNotContains(response, f'/monitoring/units/{self.unit.unit_code}/quantity-event/')

    def test_dashboard_quantity_reflects_quantity_event(self):
        from monitoring.models import QuantityEvent
        from monitoring.services import apply_quantity_event
        manager = make_manager('dash_qty_upd_mgr')
        self.client.login(username='dash_qty_upd_mgr', password=_PASSWORD)
        apply_quantity_event(
            tracking_unit=self.unit,
            event_type=QuantityEvent.EVENT_TYPE_DEATH,
            quantity_change=-5,
            user=manager,
            reason='Field culling',
        )
        response = self.client.get('/dashboard/')
        self.assertContains(response, str(10 - 5))


# ── Dashboard — archived units link ──────────────────────────────────────────

class DashboardArchivedLinkTest(TestCase):

    def test_dashboard_shows_archived_units_link(self):
        make_observer('dash_arch_obs')
        self.client.login(username='dash_arch_obs', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertContains(response, '/inventory/archived-units/')

    def test_archived_unit_not_in_active_dashboard(self):
        make_observer('dash_arch_excl_obs')
        self.client.login(username='dash_arch_excl_obs', password=_PASSWORD)
        archived = make_unit('TU-DASH-ARCH-001', is_active=False, archive_reason='dead')
        response = self.client.get('/dashboard/')
        self.assertNotContains(response, archived.unit_code)

    def test_active_unit_still_in_dashboard_after_another_archived(self):
        make_observer('dash_arch_both_obs')
        self.client.login(username='dash_arch_both_obs', password=_PASSWORD)
        active = make_unit('TU-DASH-BOTH-ACTIVE-001')
        make_unit('TU-DASH-BOTH-ARCH-001', is_active=False, archive_reason='empty')
        response = self.client.get('/dashboard/')
        self.assertContains(response, active.unit_code)
        self.assertNotContains(response, 'TU-DASH-BOTH-ARCH-001')


# ── Dashboard treatment follow-up tests ───────────────────────────────────────

def make_treatment(unit, **overrides):
    defaults = dict(
        tracking_unit=unit,
        treatment_type=Treatment.TYPE_FUNGICIDE,
        reason='Test reason',
    )
    defaults.update(overrides)
    return Treatment.objects.create(**defaults)


class DashboardTreatmentLinkTest(TestCase):

    def setUp(self):
        self.manager = make_manager(username='dash_tx_mgr')
        self.observer = make_observer(username='dash_tx_obs')
        self.unit = make_unit('TU-DASH-TX-001')

    def test_manager_sees_treatment_link_on_active_unit(self):
        self.client.login(username='dash_tx_mgr', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Treatment')

    def test_observer_does_not_see_treatment_link(self):
        self.client.login(username='dash_tx_obs', password=_PASSWORD)
        response = self.client.get('/dashboard/')
        self.assertNotContains(response, '/treatments/new/')


class DashboardFollowUpSummaryTest(TestCase):

    def setUp(self):
        self.manager = make_manager(username='dash_fu_mgr')
        self.client.login(username='dash_fu_mgr', password=_PASSWORD)
        self.unit = make_unit('TU-DASH-FU-001')

    def test_dashboard_shows_pending_followup_count(self):
        today = datetime.date.today()
        future = today + datetime.timedelta(days=7)
        make_treatment(self.unit, follow_up_date=future, outcome=Treatment.OUTCOME_PENDING)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Pending Follow-ups')
        self.assertContains(response, '1')

    def test_dashboard_shows_overdue_followup_count(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        make_treatment(self.unit, follow_up_date=yesterday, outcome=Treatment.OUTCOME_PENDING)
        response = self.client.get('/dashboard/')
        self.assertContains(response, 'Overdue Follow-ups')

    def test_overdue_followup_list_shows_unit_code(self):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        make_treatment(self.unit, follow_up_date=yesterday, outcome=Treatment.OUTCOME_PENDING)
        response = self.client.get('/dashboard/')
        self.assertContains(response, self.unit.unit_code)

    def test_resolved_treatment_not_counted_as_pending(self):
        today = datetime.date.today()
        future = today + datetime.timedelta(days=3)
        make_treatment(self.unit, follow_up_date=future, outcome=Treatment.OUTCOME_RESOLVED)
        response = self.client.get('/dashboard/')
        # Count should be 0
        self.assertContains(response, 'Pending Follow-ups')
        # The value shown should be 0 (not 1)
        context = response.context
        self.assertEqual(context['pending_followups'], 0)
