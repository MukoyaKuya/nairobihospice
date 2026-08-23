from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView, View

from apps.accounts.permissions import ClinicalStaffRequiredMixin
from apps.patients.access import authorized_patient_queryset, get_authorized_patient_or_404
from apps.patients.models import Patient

from .forms import CarePlanForm, CarePlanNeedForm, CareTeamMemberForm
from .models import CarePlan, CarePlanStatusChoices
from .services import assign_care_team_member, create_care_plan, start_episode_of_care


class CarePlanListView(LoginRequiredMixin, ListView):
    model = CarePlan
    template_name = 'care/care_plan_list.html'
    context_object_name = 'care_plans'
    paginate_by = 15

    def get_queryset(self):
        queryset = CarePlan.objects.select_related('patient', 'created_by').order_by('-created_at')
        if not self.request.user.is_clinical and not self.request.user.is_manager:
            return queryset.none()
        queryset = queryset.filter(patient__in=authorized_patient_queryset(self.request.user))
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                patient__first_name__icontains=search
            ) | queryset.filter(
                patient__last_name__icontains=search
            ) | queryset.filter(
                patient__hospice_number__icontains=search
            )
        return queryset


class CarePlanDetailView(ClinicalStaffRequiredMixin, DetailView):
    model = CarePlan
    template_name = 'care/care_plan_detail.html'
    context_object_name = 'care_plan'

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['need_form'] = CarePlanNeedForm()
        context['needs'] = self.object.needs.all()
        return context


class CarePlanCreateView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id=None):
        if getattr(request.user, 'is_receptionist', False):
            raise PermissionDenied("Receptionists are not authorized to create or modify clinical care plans.")

        patient = None
        if patient_id:
            patient = get_authorized_patient_or_404(request.user, patient_id)
            form = CarePlanForm(initial={
                'patient': patient,
                'primary_diagnosis': patient.primary_diagnosis,
                'title': 'Individualized Palliative Care Plan',
                'status': 'ACTIVE',
                'resuscitation_preference': 'Allow Natural Death (AND) / Comfort Measures'
            })
        else:
            patient_pk = request.GET.get('patient')
            if patient_pk:
                try:
                    patient = authorized_patient_queryset(request.user).get(pk=patient_pk)
                except (Patient.DoesNotExist, ValueError):
                    patient = None

            initial_data = {
                'title': 'Individualized Palliative Care Plan',
                'status': 'ACTIVE',
                'resuscitation_preference': 'Allow Natural Death (AND) / Comfort Measures'
            }
            if patient:
                initial_data['patient'] = patient
                initial_data['primary_diagnosis'] = patient.primary_diagnosis

            form = CarePlanForm(initial=initial_data)

        return render(request, 'care/care_plan_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id=None):
        if getattr(request.user, 'is_receptionist', False):
            raise PermissionDenied("Receptionists are not authorized to create or modify clinical care plans.")

        form = CarePlanForm(request.POST)
        if form.is_valid():
            if patient_id:
                patient = get_authorized_patient_or_404(request.user, patient_id)
            elif form.cleaned_data.get('patient'):
                patient = form.cleaned_data['patient']
                if not authorized_patient_queryset(request.user).filter(pk=patient.pk).exists():
                    form.add_error('patient', 'You are not authorized to create care plans for this patient.')
                    return render(request, 'care/care_plan_form.html', {'form': form, 'patient': patient})
            else:
                form.add_error('patient', 'Please select a patient.')
                return render(request, 'care/care_plan_form.html', {'form': form, 'patient': None})

            care_plan = create_care_plan(
                patient=patient,
                overall_goals=form.cleaned_data['overall_goals'],
                primary_diagnosis=form.cleaned_data.get('primary_diagnosis', ''),
                resuscitation_preference=form.cleaned_data.get('resuscitation_preference', ''),
                title=form.cleaned_data.get('title') or 'Individualized Palliative Care Plan',
                review_date=form.cleaned_data.get('review_date'),
                status=form.cleaned_data.get('status') or CarePlanStatusChoices.ACTIVE,
                user=request.user,
            )

            messages.success(request, f"Care plan created successfully for {care_plan.patient.full_name}.")
            return redirect('care:care_plan_detail', pk=care_plan.pk)

        return render(request, 'care/care_plan_form.html', {'form': form, 'patient': None})


class CarePlanNeedCreateView(ClinicalStaffRequiredMixin, View):
    def post(self, request, pk):
        if getattr(request.user, 'is_receptionist', False):
            raise PermissionDenied("Receptionists are not authorized to modify clinical care plan needs.")
        care_plan = get_object_or_404(
            CarePlan.objects.filter(patient__in=authorized_patient_queryset(request.user)), pk=pk
        )
        form = CarePlanNeedForm(request.POST)
        if form.is_valid():
            need = form.save(commit=False)
            need.care_plan = care_plan
            need.save()
            messages.success(request, "Care plan goal / intervention added successfully.")
        else:
            messages.error(request, "Could not add goal. Please check the entered data.")
        return redirect('care:care_plan_detail', pk=care_plan.pk)


class CareTeamAssignView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        if getattr(request.user, 'is_receptionist', False):
            raise PermissionDenied("Receptionists are not authorized to manage clinical care teams.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        episode = patient.episodes.filter(status='ACTIVE').first()
        if not episode:
            episode = start_episode_of_care(patient=patient, user=request.user)
        form = CareTeamMemberForm()
        team_members = episode.team_members.select_related('staff_member__user')
        return render(request, 'care/care_team_manage.html', {
            'patient': patient,
            'episode': episode,
            'form': form,
            'team_members': team_members,
        })

    def post(self, request, patient_id):
        if getattr(request.user, 'is_receptionist', False):
            raise PermissionDenied("Receptionists are not authorized to manage clinical care teams.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        episode = patient.episodes.filter(status='ACTIVE').first()
        if not episode:
            episode = start_episode_of_care(patient=patient, user=request.user)
        form = CareTeamMemberForm(request.POST)
        if form.is_valid():
            member = assign_care_team_member(
                episode=episode,
                staff_member=form.cleaned_data['staff_member'],
                role=form.cleaned_data['role'],
                is_primary=form.cleaned_data.get('is_primary', False),
                notes=form.cleaned_data.get('notes', ''),
                user=request.user,
            )
            messages.success(request, f"Assigned {member.staff_member.user.display_name} to {patient.full_name}'s care team.")
            return redirect('patients:patient_detail', pk=patient.pk)
        team_members = episode.team_members.select_related('staff_member__user')
        return render(request, 'care/care_team_manage.html', {
            'patient': patient,
            'episode': episode,
            'form': form,
            'team_members': team_members,
        })
