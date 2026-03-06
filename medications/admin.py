from django.contrib import admin
from medications.models import Medication, Prescription


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    """Админка для лекарств"""

    list_display = ['name', 'medication_type', 'created_by', 'created_at']
    list_filter = ['medication_type', 'created_at']
    search_fields = ['name', 'prescription_scheme', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'medication_type')
        }),
        ('Подробности', {
            'fields': ('prescription_scheme', 'side_effects', 'notes')
        }),
        ('Метаданные', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    """Админка для назначений"""

    list_display = ['medication', 'get_patient_name', 'doctor', 'dosage', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'doctor']
    search_fields = ['medication__name', 'patient__user__first_name', 'patient__user__last_name', 'dosage']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('patient', 'medication', 'doctor')
        }),
        ('Детали назначения', {
            'fields': ('dosage', 'frequency', 'duration', 'instructions')
        }),
        ('Даты', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_patient_name(self, obj):
        return obj.patient.user.get_full_name()
    get_patient_name.short_description = 'Пациент'
