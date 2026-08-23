from django.contrib import admin

from .models import MedicationStatement


@admin.register(MedicationStatement)
class MedicationStatementAdmin(admin.ModelAdmin):
    list_display = ('medication_name', 'patient', 'dosage', 'route', 'frequency', 'status', 'start_date')
    list_filter = ('status', 'route', 'start_date')
    search_fields = ('medication_name', 'patient__first_name', 'patient__last_name', 'patient__hospice_number', 'indication')
