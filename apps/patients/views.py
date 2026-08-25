import json
from mimetypes import guess_type

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, UpdateView, View

from apps.accounts.models import RoleChoices
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.reporting.charting import chart_json

from .access import (
    authorized_patient_queryset,
    can_manage_all_patients,
    get_authorized_patient_or_404,
    get_operational_patient_or_404,
)
from .constants import HOSPICE_DIAGNOSES
from .forms import PatientRegistrationForm, PatientUpdateForm, ReceptionistPatientUpdateForm
from .locations import KENYA_LOCATIONS
from .models import Patient, PatientStatusChoices
from .selectors import search_patients
from .services import (
    register_patient,
)


class PatientListView(LoginRequiredMixin, ListView):
    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        county = self.request.GET.get('county', '')
        sex = self.request.GET.get('sex', '')
        date_from = self.request.GET.get('date_from', '') or None
        date_to = self.request.GET.get('date_to', '') or None
        year = self.request.GET.get('year', '')
        age_group = self.request.GET.get('age_group', '')
        user = self.request.user
        clinical_search = (getattr(user, 'is_clinical', False) and not getattr(user, 'is_receptionist', False) and not getattr(user, 'is_pharmacist', False)) or can_manage_all_patients(user)
        queryset = search_patients(
            query=query,
            status=status,
            county=county,
            sex=sex,
            date_from=date_from,
            date_to=date_to,
            year=year,
            age_group=age_group,
            is_clinical=clinical_search,
        )
        if can_manage_all_patients(user) or user.is_receptionist:
            return queryset
        if user.is_clinical or getattr(user, 'is_pharmacist', False):
            return queryset.filter(pk__in=authorized_patient_queryset(user).values('pk'))
        return queryset.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_county'] = self.request.GET.get('county', '')
        context['selected_sex'] = self.request.GET.get('sex', '')
        context['selected_date_from'] = self.request.GET.get('date_from', '')
        context['selected_date_to'] = self.request.GET.get('date_to', '')
        context['selected_year'] = self.request.GET.get('year', '')
        context['selected_age_group'] = self.request.GET.get('age_group', '')
        context['is_pharmacist'] = getattr(self.request.user, 'is_pharmacist', False)
        context['is_receptionist'] = getattr(self.request.user, 'is_receptionist', False)
        context['status_choices'] = PatientStatusChoices.choices
        context['sex_choices'] = [
            ('F', 'Female'),
            ('M', 'Male'),
            ('O', 'Other'),
            ('U', 'Unknown'),
        ]
        context['years'] = list(range(2026, 2014, -1))
        return context

    def get_template_names(self):
        if self.request.htmx and not self.request.htmx.boosted:
            return ['patients/partials/patient_table_partial.html']
        return [self.template_name]


class PatientDetailView(LoginRequiredMixin, DetailView):
    """
    Patient 360° Workspace - Central clinical cockpit for Nairobi Hospice staff.
    """
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    def get_object(self):
        obj = get_operational_patient_or_404(self.request.user, self.kwargs['pk'])
        # Audit log record access
        log_audit_event(
            action=AuditAction.VIEW,
            resource_type='Patient',
            resource_id=str(obj.id),
            summary=f"Viewed patient record for {obj.full_name} ({obj.hospice_number})",
            user=self.request.user,
        )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient = self.object
        user = self.request.user
        is_pharmacist = getattr(user, 'role', '') == RoleChoices.PHARMACIST
        clinical_access = not user.is_receptionist and not is_pharmacist and (
            user.is_clinical or can_manage_all_patients(user)
        )
        context['clinical_access'] = clinical_access
        context['is_pharmacist'] = is_pharmacist

        if not clinical_access:
            context['assessments'] = []
            context['recent_assessments'] = []
            context['encounters'] = []
            context['recent_encounters'] = []
            if is_pharmacist:
                meds = list(patient.medications.select_related('prescriber').order_by('-status', '-start_date')[:100])
                context['medications'] = meds
                context['active_medications'] = [m for m in meds if m.status == 'ACTIVE']
                context['dispenses'] = list(patient.stock_movements.select_related('stock_item', 'recorded_by').order_by('-created_at')[:50])
            else:
                context['medications'] = []
                context['active_medications'] = []
                context['dispenses'] = []
            context['active_care_plan'] = None
            context['care_plan'] = None
            context['care_plans'] = []
            context['active_episode'] = None
            context['care_team'] = []
            context['recent_symptoms'] = []
            context['symptom_trends_json'] = '{}'
            context['upcoming_appointments'] = patient.appointments.filter(
                status__in=['SCHEDULED', 'CONFIRMED']
            ).select_related('staff_member').order_by('scheduled_date', 'scheduled_time')[:5]
            context['documents'] = []
            context['communications'] = []
            return context

        # Structured Assessments (Available for full Access-parity clinical dossier)
        assessments = list(patient.assessments.select_related('assessor').order_by('-assessment_date', '-created_at')[:100])
        context['assessments'] = assessments
        context['recent_assessments'] = assessments[:10]

        # Encounters (Full list & recent)
        encounters = list(patient.encounters.select_related('recorded_by').order_by('-encounter_date', '-created_at')[:100])
        context['encounters'] = encounters
        context['recent_encounters'] = encounters[:10]

        # Medications
        medications = list(patient.medications.select_related('prescriber').order_by('-status', '-start_date')[:100])
        context['medications'] = medications
        context['active_medications'] = [m for m in medications if m.status == 'ACTIVE']

        # Care Plans
        active_care_plan = patient.care_plans.filter(status='ACTIVE').first()
        context['active_care_plan'] = active_care_plan
        context['care_plan'] = active_care_plan
        context['care_plans'] = list(patient.care_plans.order_by('-created_at')[:50])

        # Episodes and Care Team
        active_episode = patient.episodes.filter(status='ACTIVE').order_by('-start_date').first()
        context['active_episode'] = active_episode
        context['care_team'] = active_episode.team_members.select_related('staff_member__user') if active_episode else []

        # Longitudinal Symptoms (Last 10 ESAS records)
        symptoms = list(patient.symptom_records.prefetch_related('scores').order_by('-recorded_at')[:100])
        context['recent_symptoms'] = symptoms[:10]

        # Symptom trends for Chart.js
        trend_records = list(reversed(symptoms))
        dates = [r.recorded_at.strftime('%d %b') for r in trend_records]
        distress_scores = [r.total_distress_score for r in trend_records]
        pain_scores = [r.pain_score_val or 0 for r in trend_records]
        context['symptom_trends_json'] = chart_json({
            'dates': dates,
            'distress_scores': distress_scores,
            'pain_scores': pain_scores,
        })

        # Upcoming Appointments
        context['upcoming_appointments'] = patient.appointments.filter(
            status__in=['SCHEDULED', 'CONFIRMED']
        ).select_related('staff_member').order_by('scheduled_date', 'scheduled_time')[:5]

        # Documents & Communications
        context['documents'] = patient.documents.select_related('uploaded_by').order_by('-uploaded_at')[:10]
        context['communications'] = patient.communications.select_related('recorded_by').order_by('-communication_date')[:10]

        return context


def kenya_locations_api(request):
    """
    Public / internal JSON API endpoint returning Kenya Counties, Sub-Counties, and Wards.
    """
    return JsonResponse(KENYA_LOCATIONS, safe=False)


class PatientCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = PatientRegistrationForm()
        clinical_access = getattr(request.user, 'is_clinical', False) or can_manage_all_patients(request.user)
        return render(request, 'patients/patient_form.html', {
            'form': form,
            'is_create': True,
            'clinical_access': clinical_access,
            'kenya_locations_json': json.dumps(KENYA_LOCATIONS),
            'hospice_diagnoses': HOSPICE_DIAGNOSES,
        })

    def post(self, request):
        clinical_access = getattr(request.user, 'is_clinical', False) or can_manage_all_patients(request.user)
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            hiv_status = cd.get('hiv_status', '') if clinical_access else ''
            primary_diagnosis = cd.get('primary_diagnosis', '') if clinical_access else ''
            allergies = cd.get('allergies', '') if clinical_access else ''
            clinical_alerts = cd.get('clinical_alerts', '') if clinical_access else ''
            chief_complaint = cd.get('chief_complaint', '') if clinical_access else ''
            past_medical_history = cd.get('past_medical_history', '') if clinical_access else ''
            family_history = cd.get('family_history', '') if clinical_access else ''
            drug_history = cd.get('drug_history', '') if clinical_access else ''

            from django.core.exceptions import ValidationError
            try:
                patient = register_patient(
                    first_name=cd['first_name'],
                    last_name=cd['last_name'],
                    middle_name=cd.get('middle_name', ''),
                    ip_op_number=cd.get('ip_op_number', ''),
                    daycare_number=cd.get('daycare_number', ''),
                    hiv_status=hiv_status,
                    referred_by=cd.get('referred_by', ''),
                    date_of_birth=cd.get('date_of_birth'),
                    sex=cd.get('sex', 'F'),
                    identification_type=cd.get('identification_type', 'NATIONAL_ID'),
                    identification_number=cd.get('identification_number', ''),
                    phone_number=cd.get('phone_number', ''),
                    alternative_phone=cd.get('alternative_phone', ''),
                    email=cd.get('email', ''),
                    address=cd.get('address', ''),
                    county=cd.get('county', 'Nairobi'),
                    sub_county=cd.get('sub_county', ''),
                    ward=cd.get('ward', ''),
                    landmark=cd.get('landmark', ''),
                    preferred_language=cd.get('preferred_language', 'English'),
                    marital_status=cd.get('marital_status', 'MARRIED'),
                    religion=cd.get('religion', ''),
                    occupation=cd.get('occupation', ''),
                    primary_diagnosis=primary_diagnosis,
                    allergies=allergies,
                    clinical_alerts=clinical_alerts,
                    notes=cd.get('notes', ''),
                    created_by=request.user,
                    nok_name=cd.get('nok_name', ''),
                    nok_relationship=cd.get('nok_relationship', ''),
                    nok_phone=cd.get('nok_phone', ''),
                    nok_address=cd.get('nok_address', ''),
                    nok_age=cd.get('nok_age'),
                    nok_gender=cd.get('nok_gender', ''),
                    caregiver_name=cd.get('caregiver_name', ''),
                    caregiver_relationship=cd.get('caregiver_relationship', ''),
                    caregiver_phone=cd.get('caregiver_phone', ''),
                    caregiver_address=cd.get('caregiver_address', ''),
                    caregiver_age=cd.get('caregiver_age'),
                    caregiver_gender=cd.get('caregiver_gender', ''),
                    caregiver_notes=cd.get('caregiver_notes', ''),
                    chief_complaint=chief_complaint,
                    past_medical_history=past_medical_history,
                    family_history=family_history,
                    drug_history=drug_history,
                    primary_nurse=cd.get('primary_nurse'),
                    primary_doctor=cd.get('primary_doctor'),
                    require_care_team=True,
                )
                messages.success(request, f"Patient {patient.full_name} registered successfully with Hospice ID {patient.hospice_number}.")
                return redirect('patients:patient_detail', pk=patient.pk)
            except ValidationError as e:
                form.add_error(None, e)
        return render(request, 'patients/patient_form.html', {
            'form': form,
            'is_create': True,
            'clinical_access': clinical_access,
            'kenya_locations_json': json.dumps(KENYA_LOCATIONS),
            'hospice_diagnoses': HOSPICE_DIAGNOSES,
        })


class PatientUpdateView(LoginRequiredMixin, UpdateView):
    model = Patient
    template_name = 'patients/patient_form.html'

    def get_form_class(self):
        if getattr(self.request.user, 'is_clinical', False) or can_manage_all_patients(self.request.user):
            return PatientUpdateForm
        return ReceptionistPatientUpdateForm

    def get_object(self, queryset=None):
        if not (self.request.user.is_receptionist or self.request.user.is_clinical or can_manage_all_patients(self.request.user)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only receptionists, clinical and management staff may edit patient records.')
        return get_operational_patient_or_404(self.request.user, self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kenya_locations_json'] = json.dumps(KENYA_LOCATIONS)
        context['hospice_diagnoses'] = HOSPICE_DIAGNOSES
        context['is_create'] = False
        context['clinical_access'] = getattr(self.request.user, 'is_clinical', False) or can_manage_all_patients(self.request.user)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit_event(
            action=AuditAction.UPDATE,
            resource_type='Patient',
            resource_id=str(self.object.id),
            summary=f"Updated details for patient {self.object.full_name}",
            user=self.request.user,
        )
        messages.success(self.request, f"Patient {self.object.full_name} updated successfully.")
        return response

    def get_success_url(self):
        return reverse('patients:patient_detail', kwargs={'pk': self.object.pk})


class PatientIDCardView(LoginRequiredMixin, DetailView):
    """
    Printable / Downloadable Patient Hospice ID Card.
    Accessible exclusively to Front Desk Receptionists and Administration.
    """
    model = Patient
    template_name = 'patients/patient_id_card.html'
    context_object_name = 'patient'

    def get_object(self):
        if not (self.request.user.is_receptionist or self.request.user.is_manager or self.request.user.is_administrator or self.request.user.is_superuser):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Patient ID cards can only be printed and issued by Front Desk Receptionists.")

        obj = super().get_object()
        log_audit_event(
            action=AuditAction.VIEW,
            resource_type='PatientIDCard',
            resource_id=str(obj.id),
            summary=f"Generated / printed Patient ID card for {obj.full_name} ({obj.hospice_number})",
            user=self.request.user,
        )
        return obj


class PatientPhotoUploadView(LoginRequiredMixin, View):
    """
    Allows Receptionists (only) to upload or update patient identification photographs.
    """
    def post(self, request, pk):
        if not (request.user.is_receptionist or request.user.is_manager or request.user.is_administrator or request.user.is_superuser):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Only Front Desk Receptionists are authorized to upload or update patient identification photographs.")

        patient = get_operational_patient_or_404(request.user, pk)
        if 'photo' in request.FILES:
            photo_file = request.FILES['photo']
            from apps.documents.malware import scan_uploaded_file
            from django.core.exceptions import ValidationError
            try:
                scan_uploaded_file(photo_file)
                patient.photo = photo_file
                patient.save(update_fields=['photo', 'updated_at'])

                log_audit_event(
                    action=AuditAction.UPDATE,
                    resource_type='PatientPhoto',
                    resource_id=str(patient.id),
                    summary=f"Uploaded identification photograph for patient {patient.full_name} ({patient.hospice_number})",
                    user=request.user,
                )
                messages.success(request, f"Patient identification photograph updated successfully for {patient.full_name}.")
            except ValidationError as exc:
                messages.error(request, str(exc.message if hasattr(exc, 'message') else exc))
        else:
            messages.error(request, "No photograph file was provided.")

        return redirect('patients:patient_detail', pk=patient.pk)


class PatientPhotoView(LoginRequiredMixin, View):
    """Serve an identification photograph only after patient authorization."""

    def get(self, request, pk):
        patient = get_operational_patient_or_404(request.user, pk)
        if not patient.photo:
            raise Http404('This patient has no photograph.')

        content_type = guess_type(patient.photo.name)[0] or 'application/octet-stream'
        response = FileResponse(patient.photo.open('rb'), content_type=content_type)
        response['Cache-Control'] = 'private, no-store'
        return response


class PatientRequestDeleteView(LoginRequiredMixin, View):
    """
    Handle deletion requests for patients.
    Staff submit a reason, creating a PatientDeletionRequest for Operations Management approval.
    """
    def post(self, request, pk):
        patient = get_operational_patient_or_404(request.user, pk)
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, "Please provide a reason for the deletion request.")
            return redirect('patients:patient_update', pk=patient.pk)

        from apps.operations.models import PatientDeletionRequest, DeletionRequestStatusChoices
        
        # Check if there is already a pending deletion request
        existing = PatientDeletionRequest.objects.filter(
            patient=patient,
            status=DeletionRequestStatusChoices.PENDING
        ).first()

        if existing:
            messages.warning(
                request,
                f"A deletion request for {patient.full_name} is already pending Operations Management review."
            )
            return redirect('patients:patient_detail', pk=patient.pk)

        deletion_req = PatientDeletionRequest.objects.create(
            patient=patient,
            patient_id_copy=patient.pk,
            patient_name=patient.full_name,
            hospice_number=patient.hospice_number,
            ip_op_number=patient.ip_op_number,
            requested_by=request.user,
            reason=reason,
            status=DeletionRequestStatusChoices.PENDING,
        )

        log_audit_event(
            action=AuditAction.UPDATE,
            resource_type='PatientDeletionRequest',
            resource_id=str(deletion_req.id),
            summary=f"Submitted deletion request for patient {patient.full_name} ({patient.hospice_number}). Reason: {reason}",
            user=request.user,
        )

        messages.success(
            request,
            f"Deletion request for {patient.full_name} ({patient.hospice_number}) has been submitted to Operations Management for approval."
        )
        return redirect('patients:patient_detail', pk=patient.pk)


def patient_search_api(request):
    """Fast JSON search endpoint for typeahead comboboxes across clinical forms."""
    if not request.user.is_authenticated:
        return JsonResponse({'results': []}, status=401)

    is_clinical = getattr(request.user, 'is_clinical', False) or can_manage_all_patients(request.user)
    q = request.GET.get('q', '').strip()

    if is_clinical:
        base_qs = authorized_patient_queryset(request.user)
    else:
        base_qs = Patient.objects.all()

    if not q:
        patients = base_qs.order_by('-registration_date', '-created_at')[:20]
    else:
        terms = q.split()
        qs = base_qs
        for term in terms:
            clean_term = term.strip()
            if clean_term:
                filters = (
                    Q(first_name__icontains=clean_term)
                    | Q(last_name__icontains=clean_term)
                    | Q(middle_name__icontains=clean_term)
                    | Q(hospice_number__icontains=clean_term)
                    | Q(ip_op_number__icontains=clean_term)
                    | Q(identification_number__icontains=clean_term)
                    | Q(phone_number__icontains=clean_term)
                    | Q(alternative_phone__icontains=clean_term)
                    | Q(county__icontains=clean_term)
                    | Q(sub_county__icontains=clean_term)
                )
                if is_clinical:
                    filters |= Q(primary_diagnosis__icontains=clean_term)
                qs = qs.filter(filters)
        patients = qs.order_by('-registration_date', '-created_at')[:60]

    results = [
        {
            'id': str(p.id),
            'full_name': p.full_name,
            'hospice_number': p.hospice_number,
            'primary_diagnosis': (p.primary_diagnosis or '') if is_clinical else '',
            'age': p.age or '',
            'sex': p.get_sex_display() if hasattr(p, 'get_sex_display') else '',
            'status': p.get_status_display() if hasattr(p, 'get_status_display') else 'Active',
        }
        for p in patients
    ]
    return JsonResponse({'results': results, 'count': len(results)})

