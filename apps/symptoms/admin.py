from django.contrib import admin

from .models import SymptomAssessmentRecord, SymptomScore


class SymptomScoreInline(admin.TabularInline):
    model = SymptomScore
    extra = 0


@admin.register(SymptomAssessmentRecord)
class SymptomAssessmentRecordAdmin(admin.ModelAdmin):
    list_display = ('recorded_at', 'patient', 'total_distress_score', 'recorded_by')
    list_filter = ('recorded_at',)
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__hospice_number')
    inlines = [SymptomScoreInline]
