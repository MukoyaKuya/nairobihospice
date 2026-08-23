from django.urls import path

from . import views

app_name = 'assessments'

urlpatterns = [
    path('', views.AssessmentListView.as_view(), name='assessment_list'),
    path('patient/<uuid:patient_id>/create/', views.AssessmentCreateView.as_view(), name='assessment_create'),
    path('<uuid:pk>/', views.AssessmentDetailView.as_view(), name='assessment_detail'),
    path('<uuid:pk>/amend/', views.AssessmentAmendView.as_view(), name='assessment_amend'),
]
