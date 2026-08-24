from django.urls import path

from . import views

app_name = 'symptoms'

urlpatterns = [
    path('', views.SymptomListView.as_view(), name='symptom_list'),
    path('patient/<uuid:patient_id>/create/', views.SymptomCreateView.as_view(), name='symptom_create'),
    path('patient/<uuid:patient_id>/trends/json/', views.SymptomTrendJsonView.as_view(), name='symptom_trends_json'),
]
