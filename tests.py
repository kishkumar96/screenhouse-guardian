"""
Project-level smoke tests: home page and health check endpoint.

Run with: python manage.py test tests
"""

import json
from django.test import TestCase


class HomePageTest(TestCase):
    def test_home_page_returns_200(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_home_page_contains_project_name(self):
        response = self.client.get('/')
        self.assertContains(response, 'Screen House Guardian')


class HealthCheckTest(TestCase):
    def test_health_check_returns_200(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)

    def test_health_check_returns_ok_json(self):
        response = self.client.get('/health/')
        self.assertEqual(response['Content-Type'], 'application/json')
        data = json.loads(response.content)
        self.assertEqual(data, {'status': 'ok'})
