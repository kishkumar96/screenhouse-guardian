"""
URL patterns for the /observe/<unit_code>/ workflow.
Included at the project root (not under /monitoring/) so QR codes can encode
a stable top-level URL like /observe/TU-CAS-0001/.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('<str:unit_code>/', views.observe, name='observe'),
    path('<str:unit_code>/timeline/', views.timeline, name='observe_timeline'),
]
