from django.urls import path
from . import views

app_name = 'qr'

urlpatterns = [
    path('', views.index, name='index'),
    path('units/<str:unit_code>/label/', views.label, name='label'),
    path('units/<str:unit_code>/generate/', views.generate, name='generate'),
]
