from django.contrib import admin

from .models import Referral


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referral_number', 'patient_name', 'referring_facility', 'priority', 'status', 'referral_date')
    list_filter = ('status', 'priority', 'referral_source', 'referral_date')
    search_fields = ('referral_number', 'patient_name', 'referring_facility', 'primary_diagnosis')
