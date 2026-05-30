from django.urls import path
from . import views

app_name = 'exports'

urlpatterns = [
    path('', views.index, name='index'),
    path('tracking-units.csv/', views.tracking_units_csv, name='tracking_units_csv'),
    path('tracking-units.xlsx/', views.tracking_units_excel, name='tracking_units_excel'),
    path('observations.csv/', views.observations_csv, name='observations_csv'),
    path('observations.xlsx/', views.observations_excel, name='observations_excel'),
    path('quantity-events.csv/', views.quantity_events_csv, name='quantity_events_csv'),
    path('quantity-events.xlsx/', views.quantity_events_excel, name='quantity_events_excel'),
    path('photo-metadata.csv/', views.photo_metadata_csv, name='photo_metadata_csv'),
    path('photo-metadata.xlsx/', views.photo_metadata_excel, name='photo_metadata_excel'),
    path('treatments.csv/', views.treatments_csv, name='treatments_csv'),
    path('treatments.xlsx/', views.treatments_excel, name='treatments_excel'),
]
