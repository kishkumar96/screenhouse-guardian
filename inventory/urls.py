from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.index, name='index'),
    path('crops/', views.crop_list, name='crops'),
    path('accessions/', views.accession_list, name='accessions'),
    path('batches/', views.batch_list, name='batches'),
]
