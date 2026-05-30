from django.test import TestCase


class ExportsIndexTest(TestCase):
    def test_index_returns_200(self):
        response = self.client.get('/exports/')
        self.assertEqual(response.status_code, 200)
