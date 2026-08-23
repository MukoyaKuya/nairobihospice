from django.urls import path

from . import views

app_name = 'reporting'

urlpatterns = [
    path('clinical/', views.ClinicalDashboardView.as_view(), name='clinical_dashboard'),
    path('management/', views.ManagementDashboardView.as_view(), name='management_dashboard'),
    path('export/patients/', views.ExportPatientsCsvView.as_view(), name='export_patients_csv'),
    path('export/encounters/', views.ExportEncountersCsvView.as_view(), name='export_encounters_csv'),
]
