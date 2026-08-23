from django.contrib import admin

from .models import Caregiver, NextOfKin, Patient


class NextOfKinInline(admin.TabularInline):
    model = NextOfKin
    extra = 0


class CaregiverInline(admin.TabularInline):
    model = Caregiver
    extra = 0


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('hospice_number', 'full_name', 'sex', 'age', 'status', 'county', 'registration_date')
    list_filter = ('status', 'sex', 'county', 'registration_date')
    search_fields = ('hospice_number', 'first_name', 'last_name', 'phone_number', 'identification_number', 'primary_diagnosis')
    inlines = [NextOfKinInline, CaregiverInline]
    date_hierarchy = 'registration_date'
    ordering = ('-registration_date',)
