from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from inventory.models import TrackingUnit


class CreatePhase1APilotSetupCommandTest(TestCase):

    def _call(self, **kwargs):
        out = StringIO()
        call_command('create_phase1a_pilot_setup', stdout=out, **kwargs)
        return out.getvalue()

    def test_command_creates_ten_tracking_units(self):
        self._call()
        self.assertEqual(TrackingUnit.objects.count(), 10)

    def test_command_creates_manager_and_observer_users(self):
        self._call()
        User = get_user_model()
        self.assertTrue(User.objects.filter(username='pilot_manager').exists())
        self.assertTrue(User.objects.filter(username='pilot_observer').exists())

    def test_command_assigns_groups(self):
        self._call()
        User = get_user_model()
        manager = User.objects.get(username='pilot_manager')
        observer = User.objects.get(username='pilot_observer')
        self.assertTrue(manager.groups.filter(name='Manager').exists())
        self.assertTrue(observer.groups.filter(name='Observer').exists())

    def test_command_sets_password_for_created_users(self):
        self._call(password='pilot-secret-456')
        User = get_user_model()
        manager = User.objects.get(username='pilot_manager')
        observer = User.objects.get(username='pilot_observer')
        self.assertTrue(manager.check_password('pilot-secret-456'))
        self.assertTrue(observer.check_password('pilot-secret-456'))

    def test_command_is_idempotent(self):
        self._call()
        self._call()
        User = get_user_model()
        self.assertEqual(TrackingUnit.objects.count(), 10)
        self.assertEqual(User.objects.filter(username='pilot_manager').count(), 1)
        self.assertEqual(User.objects.filter(username='pilot_observer').count(), 1)

    def test_command_respects_custom_usernames(self):
        self._call(manager_username='mgr_demo', observer_username='obs_demo')
        User = get_user_model()
        self.assertTrue(User.objects.filter(username='mgr_demo').exists())
        self.assertTrue(User.objects.filter(username='obs_demo').exists())

    def test_command_prints_summary(self):
        output = self._call()
        self.assertIn('Phase 1A pilot setup complete.', output)
        self.assertIn('Users created:', output)
        self.assertIn('Units created:', output)

    def test_command_creates_expected_sample_unit_codes(self):
        self._call()
        codes = set(TrackingUnit.objects.values_list('unit_code', flat=True))
        self.assertIn('TU-CAS-0001', codes)
        self.assertIn('TU-TAR-0002', codes)
        self.assertIn('TU-BAN-0002', codes)
        self.assertIn('TU-PAP-0001', codes)
