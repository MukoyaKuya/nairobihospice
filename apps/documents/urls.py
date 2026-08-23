from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('patient/<uuid:patient_id>/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('<uuid:pk>/download/', views.DocumentDownloadView.as_view(), name='document_download'),
]
