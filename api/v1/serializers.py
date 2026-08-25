from rest_framework import serializers

from apps.accounts.models import StaffProfile
from apps.appointments.models import Appointment
from apps.assessments.models import Assessment
from apps.care.models import CarePlan, CarePlanNeed
from apps.encounters.models import Encounter
from apps.medications.models import MedicationStatement
from apps.patients.access import authorized_patient_queryset
from apps.patients.models import Caregiver, NextOfKin, Patient
from apps.referrals.models import Referral
from apps.symptoms.models import SymptomAssessmentRecord, SymptomScore


class StaffProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.display_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = StaffProfile
        fields = ['id', 'name', 'email', 'role', 'department', 'license_number']
        read_only_fields = ['id', 'name', 'email']


class NextOfKinSerializer(serializers.ModelSerializer):
    class Meta:
        model = NextOfKin
        fields = ['id', 'name', 'relationship', 'phone_number', 'alternative_phone', 'email', 'is_primary']
        read_only_fields = ['id']


class CaregiverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caregiver
        fields = ['id', 'name', 'relationship', 'phone_number', 'email', 'availability', 'is_primary']
        read_only_fields = ['id']


class PatientSerializer(serializers.ModelSerializer):
    next_of_kin = NextOfKinSerializer(many=True, read_only=True)
    caregivers = CaregiverSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'hospice_number', 'first_name', 'middle_name', 'last_name', 'full_name',
            'date_of_birth', 'age', 'sex', 'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email', 'address', 'county', 'sub_county', 'landmark',
            'preferred_language', 'marital_status', 'primary_diagnosis', 'allergies', 'blood_group',
            'status', 'registration_date', 'clinical_alerts', 'next_of_kin', 'caregivers', 'created_at',
        ]
        read_only_fields = ['id', 'hospice_number', 'full_name', 'age', 'created_at']


class PatientSummarySerializer(serializers.ModelSerializer):
    """Reception-safe patient representation without clinical narrative fields."""
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'hospice_number', 'first_name', 'middle_name', 'last_name',
            'full_name', 'date_of_birth', 'age', 'sex', 'phone_number',
            'alternative_phone', 'email', 'address', 'county', 'sub_county',
            'landmark', 'preferred_language', 'marital_status', 'status',
            'registration_date', 'created_at',
        ]
        read_only_fields = ['id', 'hospice_number', 'full_name', 'age', 'status', 'created_at']


class PatientBoundSerializerMixin:
    """Prevent API writes from moving a record across patient access boundaries."""

    def validate_patient(self, patient):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError('An authenticated staff user is required.')
        if self.instance is not None and self.instance.patient_id != patient.pk:
            raise serializers.ValidationError('A clinical record cannot be reassigned to another patient.')
        if not authorized_patient_queryset(request.user).filter(pk=patient.pk).exists():
            raise serializers.ValidationError('You are not authorized to access this patient.')
        return patient


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = Referral
        fields = [
            'id', 'referral_number', 'patient_name', 'date_of_birth', 'sex',
            'phone_number', 'alternative_phone', 'address', 'county', 'sub_county', 'landmark',
            'referral_source', 'referring_facility', 'referring_clinician_name',
            'referring_clinician_phone', 'referring_clinician_email',
            'referral_date', 'priority', 'status', 'primary_diagnosis',
            'reason_for_referral', 'clinical_summary', 'current_medications',
            'assigned_reviewer', 'review_notes', 'converted_patient', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'referral_number', 'created_at', 'updated_at']


class CarePlanNeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarePlanNeed
        fields = [
            'id', 'care_plan', 'category', 'problem_description', 'goal',
            'interventions', 'responsible_discipline', 'target_date',
            'is_resolved', 'outcome_notes', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CarePlanSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    needs = CarePlanNeedSerializer(many=True, read_only=True)

    class Meta:
        model = CarePlan
        fields = [
            'id', 'patient', 'episode', 'title', 'primary_diagnosis',
            'overall_goals', 'resuscitation_preference', 'status',
            'review_date', 'needs', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EncounterSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.display_name', read_only=True)

    class Meta:
        model = Encounter
        fields = [
            'id', 'patient', 'episode', 'encounter_type', 'encounter_date',
            'location', 'reason', 'clinical_notes', 'interventions_performed',
            'next_followup_date', 'next_followup_plan', 'recorded_by',
            'recorded_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'recorded_by_name', 'created_at', 'updated_at']


class AssessmentSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    assessor_name = serializers.CharField(source='assessor.display_name', read_only=True)
    pain_site = serializers.CharField(source='structured_data.pain_site', read_only=True, allow_null=True)
    pain_character = serializers.CharField(source='structured_data.pain_character', read_only=True, allow_null=True)
    psychosocial_needs = serializers.CharField(source='structured_data.psychosocial_needs', read_only=True, allow_null=True)
    spiritual_concerns = serializers.CharField(source='structured_data.spiritual_concerns', read_only=True, allow_null=True)

    class Meta:
        model = Assessment
        fields = [
            'id', 'patient', 'assessment_type', 'assessment_date',
            'pain_score', 'pain_site', 'pain_character', 'pps_score',
            'ecog_score', 'psychosocial_needs', 'spiritual_concerns',
            'clinical_summary', 'assessor', 'assessor_name',
            'next_review_date', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'assessor', 'assessor_name', 'created_at', 'updated_at']


class SymptomScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = SymptomScore
        fields = ['id', 'symptom_type', 'score', 'notes']
        read_only_fields = ['id']


class SymptomRecordSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    scores = SymptomScoreSerializer(many=True, read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.display_name', read_only=True)

    class Meta:
        model = SymptomAssessmentRecord
        fields = [
            'id', 'patient', 'recorded_at', 'total_distress_score',
            'clinical_notes', 'recorded_by', 'recorded_by_name', 'scores', 'created_at',
        ]
        # total_distress_score is derived from the ESAS scores, never client-supplied.
        read_only_fields = ['id', 'recorded_by_name', 'created_at', 'total_distress_score']


class MedicationStatementSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    notes = serializers.CharField(source='discontinuation_reason', read_only=True)

    class Meta:
        model = MedicationStatement
        fields = [
            'id', 'patient', 'medication_name', 'dosage', 'route',
            'frequency', 'indication', 'start_date', 'end_date',
            'status', 'prescriber', 'prescriber_name',
            'instructions_for_caregiver', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'prescriber', 'prescriber_name', 'created_at', 'updated_at']


class AppointmentSerializer(PatientBoundSerializerMixin, serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    staff_name = serializers.CharField(source='staff_member.user.display_name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'staff_member', 'staff_name',
            'appointment_type', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'location', 'reason', 'notes',
            'status', 'outcome_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'patient_name', 'staff_name', 'created_at', 'updated_at']


class AppointmentSummarySerializer(serializers.ModelSerializer):
    """Reception-safe scheduling representation without clinical reasons or outcomes."""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    staff_name = serializers.CharField(source='staff_member.user.display_name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'staff_member', 'staff_name',
            'appointment_type', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'location', 'status', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'patient_name', 'staff_name', 'created_at', 'updated_at']
