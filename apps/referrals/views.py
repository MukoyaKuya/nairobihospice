from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView, View

from .access import can_review_referrals, get_referral_or_404, referral_queryset_for_user
from .forms import ReferralConvertForm, ReferralForm, ReferralReviewForm
from .models import Referral, ReferralPriorityChoices, ReferralStatusChoices
from .selectors import filter_referrals
from .services import convert_referral_to_patient, create_referral


class ReferralListView(LoginRequiredMixin, ListView):
    model = Referral
    template_name = 'referrals/referral_list.html'
    context_object_name = 'referrals'
    paginate_by = 20

    def get_queryset(self):
        q = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        priority = self.request.GET.get('priority', '')
        clinical_access = bool(self.request.user.is_clinical or self.request.user.is_manager or self.request.user.is_superuser)
        return filter_referrals(query=q, status=status, priority=priority, is_clinical=clinical_access).filter(
            pk__in=referral_queryset_for_user(self.request.user).values('pk')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_priority'] = self.request.GET.get('priority', '')
        context['status_choices'] = ReferralStatusChoices.choices
        context['priority_choices'] = ReferralPriorityChoices.choices
        context['clinical_access'] = bool(self.request.user.is_clinical or self.request.user.is_manager or self.request.user.is_superuser)
        return context


class ReferralDetailView(LoginRequiredMixin, DetailView):
    model = Referral
    template_name = 'referrals/referral_detail.html'
    context_object_name = 'referral'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['review_form'] = ReferralReviewForm(instance=self.object)
        context['convert_form'] = ReferralConvertForm()
        context['can_review'] = can_review_referrals(self.request.user)
        context['clinical_access'] = bool(self.request.user.is_clinical or self.request.user.is_manager or self.request.user.is_superuser)
        return context

    def get_object(self, queryset=None):
        return get_referral_or_404(self.request.user, self.kwargs['pk'])


class ReferralCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if getattr(request.user, 'is_pharmacist', False):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Pharmacists are not authorized to create referrals.')
        from apps.patients.constants import HOSPICE_DIAGNOSES
        clinical_access = bool(request.user.is_clinical or request.user.is_manager or request.user.is_superuser)
        form = ReferralForm(clinical_access=clinical_access)
        return render(request, 'referrals/referral_form.html', {
            'form': form, 
            'is_create': True,
            'clinical_access': clinical_access,
            'hospice_diagnoses': HOSPICE_DIAGNOSES,
        })

    def post(self, request):
        if getattr(request.user, 'is_pharmacist', False):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Pharmacists are not authorized to create referrals.')
        from apps.patients.constants import HOSPICE_DIAGNOSES
        clinical_access = bool(request.user.is_clinical or request.user.is_manager or request.user.is_superuser)
        form = ReferralForm(request.POST, clinical_access=clinical_access)
        if form.is_valid():
            cd = form.cleaned_data
            primary_diag = cd['primary_diagnosis'] if clinical_access else 'Pending Clinical Review'
            clinical_sum = cd.get('clinical_summary', '') if clinical_access else ''
            current_meds = cd.get('current_medications', '') if clinical_access else ''

            handled = {'patient_name', 'referring_facility', 'primary_diagnosis', 'reason_for_referral', 'clinical_summary', 'current_medications'}
            referral = create_referral(
                patient_name=cd['patient_name'],
                referring_facility=cd['referring_facility'],
                primary_diagnosis=primary_diag,
                reason_for_referral=cd['reason_for_referral'],
                clinical_summary=clinical_sum,
                current_medications=current_meds,
                created_by=request.user,
                **{key: value for key, value in cd.items() if key not in handled},
            )
            messages.success(request, f"Referral {referral.referral_number} registered successfully.")
            return redirect('referrals:referral_detail', pk=referral.pk)
        return render(request, 'referrals/referral_form.html', {'form': form, 'is_create': True, 'clinical_access': clinical_access})


class ReferralReviewView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not can_review_referrals(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only clinical and management staff may review referrals.')
        referral = get_referral_or_404(request.user, pk)
        form = ReferralReviewForm(request.POST, instance=referral)
        if form.is_valid():
            rev = form.save(commit=False)
            rev.assigned_reviewer = request.user
            from django.utils import timezone
            rev.reviewed_at = timezone.now()
            rev.save()
            messages.success(request, f"Referral {referral.referral_number} review updated to {rev.get_status_display()}.")
        return redirect('referrals:referral_detail', pk=referral.pk)


class ReferralConvertView(LoginRequiredMixin, View):
    """
    Converts accepted referral into a registered patient and active care episode.
    Requires explicit assignment of primary nurse and primary doctor.
    """
    def post(self, request, pk):
        if not can_review_referrals(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('Only clinical and management staff may convert referrals.')
        referral = get_referral_or_404(request.user, pk)
        if referral.status == ReferralStatusChoices.CONVERTED and referral.converted_patient:
            messages.info(request, "This referral has already been converted to a patient record.")
            return redirect('patients:patient_detail', pk=referral.converted_patient.pk)

        form = ReferralConvertForm(request.POST)
        if form.is_valid():
            primary_nurse = form.cleaned_data['primary_nurse']
            primary_doctor = form.cleaned_data['primary_doctor']
            patient = convert_referral_to_patient(
                referral=referral,
                user=request.user,
                primary_nurse=primary_nurse,
                primary_doctor=primary_doctor,
            )
            messages.success(
                request,
                f"Successfully converted referral into patient {patient.full_name} ({patient.hospice_number}) with assigned primary care team."
            )
            return redirect('patients:patient_detail', pk=patient.pk)
        
        # If form validation fails, redirect with error
        err_msg = "Care team assignment is required: " + "; ".join(
            [f"{f}: {e[0]}" for f, e in form.errors.items()]
        )
        messages.error(request, err_msg)
        return redirect('referrals:referral_detail', pk=referral.pk)
