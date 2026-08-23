from django.urls import path

from . import views

app_name = 'medications'

urlpatterns = [
    path('', views.MedicationListView.as_view(), name='medication_list'),
    path('patient/<uuid:patient_id>/create/', views.MedicationCreateView.as_view(), name='medication_create'),
    path('<uuid:pk>/update-status/', views.MedicationStatusUpdateView.as_view(), name='medication_status_update'),
]
