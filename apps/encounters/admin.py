from django.contrib import admin

from .models import Encounter


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ('encounter_date', 'encounter_type', 'patient', 'location', 'recorded_by')
    list_filter = ('encounter_type', 'encounter_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__hospice_number', 'reason', 'clinical_notes')
