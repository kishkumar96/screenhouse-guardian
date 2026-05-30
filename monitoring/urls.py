from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.index, name='index'),
    path('units/<str:unit_code>/quantity-event/', views.create_quantity_event, name='create_quantity_event'),
    path('units/<str:unit_code>/treatments/new/', views.create_treatment, name='create_treatment'),
    path('treatments/<int:treatment_id>/outcome/', views.update_treatment_outcome, name='update_treatment_outcome'),
    # Daily rounds
    path('rounds/', views.round_list, name='round_list'),
    path('rounds/new/', views.round_create, name='round_create'),
    path('rounds/<int:round_id>/', views.round_detail, name='round_detail'),
    path('rounds/<int:round_id>/edit/', views.round_edit, name='round_edit'),
]
