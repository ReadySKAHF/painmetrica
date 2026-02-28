from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User, DoctorProfile, PatientProfile, OTPCode


class DoctorProfileInline(admin.StackedInline):
    """Inline для профиля доктора"""
    model = DoctorProfile
    can_delete = False
    verbose_name_plural = 'Профиль доктора'


class PatientProfileInline(admin.StackedInline):
    """Inline для профиля пациента"""
    model = PatientProfile
    can_delete = False
    verbose_name_plural = 'Профиль пациента'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админка для кастомной модели пользователя"""

    list_display = ['email', 'get_full_name', 'user_type', 'is_email_verified', 'is_staff', 'is_active']
    list_filter = ['user_type', 'is_email_verified', 'is_staff', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'middle_name']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'middle_name', 'last_name')}),
        ('Тип пользователя', {'fields': ('user_type', 'is_email_verified')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'user_type', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    def get_inline_instances(self, request, obj=None):
        """Показываем нужный inline в зависимости от типа пользователя"""
        if obj is None:
            return []
        if obj.user_type == 'doctor':
            return [DoctorProfileInline(self.model, self.admin_site)]
        elif obj.user_type == 'patient':
            return [PatientProfileInline(self.model, self.admin_site)]
        return []


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """Админка для OTP кодов"""

    list_display = ['user', 'code', 'purpose', 'is_used', 'expires_at', 'created_at']
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['user__email', 'code']
    readonly_fields = ['user', 'code', 'purpose', 'is_used', 'expires_at', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        """Запрещаем создание через админку"""
        return False

    def has_change_permission(self, request, obj=None):
        """Только просмотр"""
        return False
