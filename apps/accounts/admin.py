from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StaffProfile, User


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (StaffProfileInline,)
    list_display = ('email', 'first_name', 'last_name', 'get_role', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'staff_profile__role')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    def get_role(self, obj):
        return obj.role
    get_role.short_description = 'Role'


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'license_number', 'is_active_staff')
    list_filter = ('role', 'department', 'is_active_staff')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'license_number')


from .models import SecurityConfiguration


@admin.register(SecurityConfiguration)
class SecurityConfigurationAdmin(admin.ModelAdmin):
    list_display = ('mfa_enabled', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at',)

