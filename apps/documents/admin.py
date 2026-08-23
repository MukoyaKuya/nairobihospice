from django.contrib import admin

from .models import PatientDocument


@admin.register(PatientDocument)
class PatientDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'patient', 'category', 'file_size_bytes', 'uploaded_by', 'uploaded_at')
    list_filter = ('category', 'uploaded_at')
    search_fields = ('title', 'patient__first_name', 'patient__last_name', 'patient__hospice_number')
