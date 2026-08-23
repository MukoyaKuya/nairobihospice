from django.urls import path

from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.PatientListView.as_view(), name='patient_list'),
    path('register/', views.PatientCreateView.as_view(), name='patient_register'),
    path('api/locations/', views.kenya_locations_api, name='api_locations'),
    path('<uuid:pk>/', views.PatientDetailView.as_view(), name='patient_detail'),
    path('<uuid:pk>/edit/', views.PatientUpdateView.as_view(), name='patient_update'),
    path('<uuid:pk>/card/', views.PatientIDCardView.as_view(), name='patient_id_card'),
    path('<uuid:pk>/upload-photo/', views.PatientPhotoUploadView.as_view(), name='patient_photo_upload'),
    path('<uuid:pk>/photo/', views.PatientPhotoView.as_view(), name='patient_photo'),
]
