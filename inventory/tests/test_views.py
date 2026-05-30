from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase


PASSWORD = 'testpass123'


def make_observer(username='inv_observer'):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD)
    group, _ = Group.objects.get_or_create(name='Observer')
    user.groups.add(group)
    return user


class InventoryIndexTest(TestCase):
    def test_index_redirects_anonymous_user_to_login(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_index_returns_200_for_observer(self):
        make_observer()
        self.client.login(username='inv_observer', password=PASSWORD)
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)
