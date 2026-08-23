from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('scheduled_date', 'scheduled_time', 'appointment_type', 'patient', 'staff_member', 'status')
    list_filter = ('status', 'appointment_type', 'scheduled_date')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__hospice_number', 'staff_member__user__first_name')
