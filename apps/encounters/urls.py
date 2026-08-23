from django.urls import path

from . import views

app_name = 'encounters'

urlpatterns = [
    path('', views.EncounterListView.as_view(), name='encounter_list'),
    path('patient/<uuid:patient_id>/create/', views.EncounterCreateView.as_view(), name='encounter_create'),
    path('<uuid:pk>/', views.EncounterDetailView.as_view(), name='encounter_detail'),
]
