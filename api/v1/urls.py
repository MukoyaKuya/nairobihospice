from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'patients', views.PatientViewSet)
router.register(r'referrals', views.ReferralViewSet)
router.register(r'care-plans', views.CarePlanViewSet)
router.register(r'encounters', views.EncounterViewSet)
router.register(r'assessments', views.AssessmentViewSet)
router.register(r'symptoms', views.SymptomRecordViewSet)
router.register(r'medications', views.MedicationStatementViewSet)
router.register(r'appointments', views.AppointmentViewSet)

app_name = 'api_v1'

urlpatterns = [
    path('', include(router.urls)),
]
