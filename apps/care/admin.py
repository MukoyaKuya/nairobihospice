from django.contrib import admin

from .models import CarePlan, CarePlanNeed, CareTeamMember, EpisodeOfCare


class CareTeamMemberInline(admin.TabularInline):
    model = CareTeamMember
    extra = 0


class CarePlanNeedInline(admin.TabularInline):
    model = CarePlanNeed
    extra = 0


@admin.register(EpisodeOfCare)
class EpisodeOfCareAdmin(admin.ModelAdmin):
    list_display = ('patient', 'start_date', 'status', 'end_date')
    list_filter = ('status', 'start_date')
    inlines = [CareTeamMemberInline]


@admin.register(CarePlan)
class CarePlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient', 'status', 'review_date', 'created_at')
    list_filter = ('status', 'review_date')
    inlines = [CarePlanNeedInline]
