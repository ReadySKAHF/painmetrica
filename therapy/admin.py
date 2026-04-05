from django.contrib import admin
from therapy.models import Therapy, TherapyNote


class TherapyNoteInline(admin.TabularInline):
    model = TherapyNote
    extra = 0
    readonly_fields = ('doctor', 'created_at', 'updated_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Therapy)
class TherapyAdmin(admin.ModelAdmin):
    list_display = ('name', 'therapy_type', 'created_by', 'created_at')
    search_fields = ('name', 'therapy_type')
    inlines = [TherapyNoteInline]
