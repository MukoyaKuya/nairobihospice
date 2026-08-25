from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from apps.accounts.permissions import (
    IsAppointmentApiPermission,
    IsAuthenticatedApiPermission,
    IsClinicalOrManagerPermission,
    IsClinicalStaffPermission,
    IsPharmacistOrClinicalPermission,
)
from apps.appointments.models import Appointment
from apps.assessments.models import Assessment
from apps.care.models import CarePlan
from apps.encounters.models import Encounter
from apps.medications.models import MedicationStatement
from apps.patients.access import authorized_patient_queryset, can_manage_all_patients
from apps.patients.models import Patient
from apps.referrals.access import referral_queryset_for_user
from apps.referrals.models import Referral
from apps.symptoms.models import SymptomAssessmentRecord

from .serializers import (
    AppointmentSerializer,
    AppointmentSummarySerializer,
    AssessmentSerializer,
    CarePlanSerializer,
    EncounterSerializer,
    MedicationStatementSerializer,
    PatientSerializer,
    PatientSummarySerializer,
    ReferralSerializer,
    SymptomRecordSerializer,
)


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().prefetch_related('next_of_kin', 'caregivers').order_by('-registration_date')
    permission_classes = [IsAuthenticatedApiPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'sex', 'county']
    search_fields = ['hospice_number', 'first_name', 'last_name', 'phone_number', 'identification_number', 'primary_diagnosis']
    ordering_fields = ['registration_date', 'last_name', 'hospice_number']

    def get_queryset(self):
        user = self.request.user
        if can_manage_all_patients(user) or user.is_receptionist:
            return self.queryset
        if user.is_clinical:
            return self.queryset.filter(pk__in=authorized_patient_queryset(user).values('pk'))
        return self.queryset.none()

    def get_serializer_class(self):
        if getattr(self.request.user, 'is_clinical', False) or can_manage_all_patients(self.request.user):
            return PatientSerializer
        return PatientSummarySerializer

    def filter_queryset(self, queryset):
        user = self.request.user
        if not (getattr(user, 'is_clinical', False) or can_manage_all_patients(user)):
            self.search_fields = ['hospice_number', 'first_name', 'last_name', 'phone_number', 'identification_number']
        else:
            self.search_fields = ['hospice_number', 'first_name', 'last_name', 'phone_number', 'identification_number', 'primary_diagnosis']
        return super().filter_queryset(queryset)


class ReferralViewSet(viewsets.ModelViewSet):
    queryset = Referral.objects.all().order_by('-referral_date')
    serializer_class = ReferralSerializer
    permission_classes = [IsClinicalOrManagerPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'referral_source']
    search_fields = ['referral_number', 'patient_name', 'referring_facility', 'primary_diagnosis']

    def get_queryset(self):
        return self.queryset.filter(pk__in=referral_queryset_for_user(self.request.user).values('pk'))


class CarePlanViewSet(viewsets.ModelViewSet):
    queryset = CarePlan.objects.all().prefetch_related('needs').order_by('-created_at')
    serializer_class = CarePlanSerializer
    permission_classes = [IsClinicalStaffPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'status']
    search_fields = ['title', 'primary_diagnosis', 'overall_goals']

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))


class EncounterViewSet(viewsets.ModelViewSet):
    queryset = Encounter.objects.all().select_related('patient', 'recorded_by').order_by('-encounter_date')
    serializer_class = EncounterSerializer
    permission_classes = [IsClinicalStaffPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'encounter_type', 'encounter_date']
    search_fields = ['reason', 'clinical_notes', 'interventions_performed']

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class AssessmentViewSet(viewsets.ModelViewSet):
    queryset = Assessment.objects.all().select_related('patient', 'assessor').order_by('-assessment_date')
    serializer_class = AssessmentSerializer
    permission_classes = [IsClinicalStaffPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'assessment_type', 'assessment_date']
    search_fields = ['clinical_summary']

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def perform_create(self, serializer):
        serializer.save(assessor=self.request.user)


class SymptomRecordViewSet(viewsets.ModelViewSet):
    queryset = SymptomAssessmentRecord.objects.all().prefetch_related('scores').select_related('patient', 'recorded_by').order_by('-recorded_at')
    serializer_class = SymptomRecordSerializer
    permission_classes = [IsClinicalStaffPermission]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['patient']

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class MedicationStatementViewSet(viewsets.ModelViewSet):
    queryset = MedicationStatement.objects.all().select_related('patient').order_by('-start_date')
    serializer_class = MedicationStatementSerializer
    permission_classes = [IsPharmacistOrClinicalPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'status', 'route']
    search_fields = ['medication_name', 'indication']

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def perform_create(self, serializer):
        serializer.save(prescriber=self.request.user)


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().select_related('patient', 'staff_member__user').order_by('scheduled_date', 'scheduled_time')
    serializer_class = AppointmentSerializer
    permission_classes = [IsAppointmentApiPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['patient', 'staff_member', 'status', 'appointment_type', 'scheduled_date']
    search_fields = ['reason', 'notes']

    def get_serializer_class(self):
        user = self.request.user
        if getattr(user, 'is_clinical', False) or getattr(user, 'is_manager', False):
            return AppointmentSerializer
        return AppointmentSummarySerializer

    def get_queryset(self):
        from apps.patients.access import authorized_appointment_queryset
        return self.queryset.filter(pk__in=authorized_appointment_queryset(self.request.user).values('pk'))
