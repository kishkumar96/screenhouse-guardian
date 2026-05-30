from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.index, name='index'),
    path('units/<str:unit_code>/quantity-event/', views.create_quantity_event, name='create_quantity_event'),
]
