from django.urls import path

from . import views

app_name = 'appointments'

urlpatterns = [
    path('', views.AppointmentCalendarView.as_view(), name='calendar'),
    path('routes/', views.HomeRouteLogisticsView.as_view(), name='home_routes'),
    path('patient/<uuid:patient_id>/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('<uuid:pk>/update-status/', views.AppointmentStatusUpdateView.as_view(), name='appointment_update_status'),
    path('<uuid:pk>/request-delete/', views.AppointmentDeletionRequestCreateView.as_view(), name='appointment_request_delete'),
]
