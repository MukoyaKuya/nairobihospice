from django.urls import path

from . import views

app_name = 'communications'

urlpatterns = [
    path('patient/<uuid:patient_id>/create/', views.CommunicationCreateView.as_view(), name='communication_create'),
]
