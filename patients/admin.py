from django.contrib import admin
from patients.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    """Админка для пациентов"""

    list_display = ['get_patient_name', 'assigned_doctor', 'created_at']
    list_filter = ['assigned_doctor', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'medical_history']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'assigned_doctor')
        }),
        ('Медицинские данные', {
            'fields': ('medical_history', 'notes')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_patient_name(self, obj):
        """Получение имени пациента"""
        return obj.user.get_full_name()
    get_patient_name.short_description = 'Пациент'
