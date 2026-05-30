from django.test import TestCase


class InventoryIndexTest(TestCase):
    def test_index_returns_200(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)
