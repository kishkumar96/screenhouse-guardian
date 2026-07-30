from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),
    path('crops/', views.crop_list, name='crops'),
    path('accessions/', views.accession_list, name='accessions'),
    path('batches/', views.batch_list, name='batches'),
    path('units/<str:unit_code>/archive/', views.archive_tracking_unit, name='archive_tracking_unit'),
    path('archived-units/', views.archived_tracking_units, name='archived_tracking_units'),
    path('units/<str:unit_code>/move/', views.move_tracking_unit, name='move_tracking_unit'),
    path('survival/', views.survival_report, name='survival_report'),
]
