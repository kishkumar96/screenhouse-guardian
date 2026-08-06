from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('', views.index, name='index'),
    path('units/<str:unit_code>/quantity-event/', views.create_quantity_event, name='create_quantity_event'),
    path('units/<str:unit_code>/treatments/new/', views.create_treatment, name='create_treatment'),
    path('units/<str:unit_code>/distribute/', views.create_distribution, name='create_distribution'),
    path('units/<str:unit_code>/propagate/', views.create_propagation, name='create_propagation'),
    path('treatments/<int:treatment_id>/outcome/', views.update_treatment_outcome, name='update_treatment_outcome'),
    # Daily rounds
    path('rounds/', views.round_list, name='round_list'),
    path('rounds/new/', views.round_create, name='round_create'),
    path('rounds/<int:round_id>/', views.round_detail, name='round_detail'),
    path('rounds/<int:round_id>/edit/', views.round_edit, name='round_edit'),
    # Follow-up management
    path('follow-ups/', views.follow_up_list, name='follow_up_list'),
    # Weekly report
    path('reports/weekly/', views.weekly_report, name='weekly_report'),
    # Inventory reconciliation
    path('reconcile/', views.reconcile_inventory, name='reconcile_inventory'),
    # Environmental logs
    path('environmental-logs/', views.environmental_log_list, name='environmental_log_list'),
    path('environmental-logs/record/', views.record_environmental_log_view, name='record_environmental_log'),
    path('environmental-logs/summary/', views.environmental_summary, name='environmental_summary'),
]
