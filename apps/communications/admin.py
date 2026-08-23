from django.contrib import admin

from .models import CommunicationRecord


@admin.register(CommunicationRecord)
class CommunicationRecordAdmin(admin.ModelAdmin):
    list_display = ('communication_date', 'patient', 'communication_type', 'contact_person', 'recorded_by')
    list_filter = ('communication_type', 'communication_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'contact_person', 'summary')
