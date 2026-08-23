from django.urls import path

from . import views

app_name = 'appointments'

urlpatterns = [
    path('', views.AppointmentCalendarView.as_view(), name='calendar'),
    path('patient/<uuid:patient_id>/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('<uuid:pk>/update-status/', views.AppointmentStatusUpdateView.as_view(), name='appointment_update_status'),
]
