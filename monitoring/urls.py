from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.index, name='index'),
    path('units/<str:unit_code>/quantity-event/', views.create_quantity_event, name='create_quantity_event'),
    path('units/<str:unit_code>/treatments/new/', views.create_treatment, name='create_treatment'),
    path('treatments/<int:treatment_id>/outcome/', views.update_treatment_outcome, name='update_treatment_outcome'),
]
