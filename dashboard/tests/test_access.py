"""
Access control tests for Ticket 009.

Tests anonymous redirects, Observer access, Manager access,
login page availability, and base template auth state.
"""

import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from inventory.models import TrackingUnit

User = get_user_model()

_PASSWORD = 'testpass123'


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user(username, group_name=None):
    user = User.objects.create_user(username=username, password=_PASSWORD)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


def make_observer(username='obs_acc'):
    return make_user(username, 'Observer')


def make_manager(username='mgr_acc'):
    return make_user(username, 'Manager')


def make_unit(unit_code='TU-ACC-001'):
    return TrackingUnit.objects.create(
        unit_code=unit_code,
        unit_type=TrackingUnit.UNIT_TYPE_CONTAINER,
        crop_name='Test Crop',
        quantity=5,
    )


# ── Anonymous redirects ───────────────────────────────────────────────────────

class AnonymousAccessTest(TestCase):
    """Anonymous requests to protected views must redirect to login."""

    def _assert_redirects_to_login(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302, f'Expected 302 for {url}')
        self.assertIn('/accounts/login/', response['Location'])

    def test_dashboard_redirects_anonymous(self):
        self._assert_redirects_to_login('/dashboard/')

    def test_observe_form_redirects_anonymous(self):
        unit = make_unit('TU-ANON-OBS-001')
        self._assert_redirects_to_login(f'/observe/{unit.unit_code}/')

    def test_timeline_redirects_anonymous(self):
        unit = make_unit('TU-ANON-TL-001')
        self._assert_redirects_to_login(f'/observe/{unit.unit_code}/timeline/')

    def test_qr_label_redirects_anonymous(self):
        unit = make_unit('TU-ANON-QR-001')
        self._assert_redirects_to_login(f'/qr/units/{unit.unit_code}/label/')

    def test_export_index_redirects_anonymous(self):
        self._assert_redirects_to_login('/exports/')


# ── Observer access ───────────────────────────────────────────────────────────

class ObserverAccessTest(TestCase):

    def setUp(self):
        self.user = make_observer()
        self.client.login(username='obs_acc', password=_PASSWORD)
        self.unit = make_unit('TU-OBS-ACC-001')

    def test_observer_can_access_dashboard(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_observer_can_access_observe_form(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/')
        self.assertEqual(response.status_code, 200)

    def test_observer_can_access_timeline(self):
        response = self.client.get(f'/observe/{self.unit.unit_code}/timeline/')
        self.assertEqual(response.status_code, 200)

    def test_observer_can_access_qr_label(self):
        response = self.client.get(f'/qr/units/{self.unit.unit_code}/label/')
        self.assertEqual(response.status_code, 200)

    def test_observer_cannot_access_export_index(self):
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 403)

    def test_observer_cannot_access_export_csv(self):
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertEqual(response.status_code, 403)

    def test_observer_cannot_generate_qr(self):
        response = self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')
        self.assertEqual(response.status_code, 403)


# ── Manager access ────────────────────────────────────────────────────────────

class ManagerAccessTest(TestCase):

    def setUp(self):
        self.user = make_manager()
        self.client.login(username='mgr_acc', password=_PASSWORD)
        self.unit = make_unit('TU-MGR-ACC-001')

    def test_manager_can_access_dashboard(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_export_index(self):
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_export_csv(self):
        response = self.client.get('/exports/tracking-units.csv/')
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_export_excel(self):
        response = self.client.get('/exports/tracking-units.xlsx/')
        self.assertEqual(response.status_code, 200)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_manager_can_generate_qr(self):
        response = self.client.post(f'/qr/units/{self.unit.unit_code}/generate/')
        self.assertIn(response.status_code, [200, 302])
        self.unit.refresh_from_db()
        self.assertTrue(self.unit.qr_code)


# ── Login page ────────────────────────────────────────────────────────────────

class LoginPageTest(TestCase):

    def test_login_page_returns_200(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_login_page_contains_form(self):
        response = self.client.get('/accounts/login/')
        self.assertContains(response, '<form')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_login_redirects_after_valid_credentials(self):
        make_observer('login_user')
        response = self.client.post('/accounts/login/', {
            'username': 'login_user',
            'password': _PASSWORD,
        })
        self.assertEqual(response.status_code, 302)

    def test_login_respects_next_parameter(self):
        make_observer('next_user')
        response = self.client.post('/accounts/login/?next=/dashboard/', {
            'username': 'next_user',
            'password': _PASSWORD,
        })
        self.assertRedirects(
            response,
            '/dashboard/',
            fetch_redirect_response=False,
        )

    def test_password_reset_url_is_not_exposed(self):
        response = self.client.get('/accounts/password_reset/')
        self.assertEqual(response.status_code, 404)


# ── Base template auth state ──────────────────────────────────────────────────

class BaseTemplateAuthTest(TestCase):

    def test_base_shows_login_link_when_anonymous(self):
        response = self.client.get('/')
        self.assertContains(response, '/accounts/login/')

    def test_base_shows_username_when_logged_in(self):
        make_observer('basetest_obs')
        self.client.login(username='basetest_obs', password=_PASSWORD)
        response = self.client.get('/')
        self.assertContains(response, 'basetest_obs')

    def test_base_shows_logout_when_logged_in(self):
        make_observer('basetest_logout')
        self.client.login(username='basetest_logout', password=_PASSWORD)
        response = self.client.get('/')
        self.assertContains(response, 'logout')
