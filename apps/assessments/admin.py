from django.contrib import admin

from .models import Assessment, AssessmentAmendment


class AssessmentAmendmentInline(admin.TabularInline):
    model = AssessmentAmendment
    extra = 0
    readonly_fields = ('amended_by', 'amended_at', 'reason_for_amendment', 'previous_content', 'amended_notes')


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('assessment_date', 'assessment_type', 'patient', 'pain_score', 'pps_score', 'assessor')
    list_filter = ('assessment_type', 'assessment_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__hospice_number', 'clinical_summary')
    inlines = [AssessmentAmendmentInline]
