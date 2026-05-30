from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.template.response import TemplateResponse

from accounts.models import User, DoctorProfile, PatientProfile, OTPCode, UserSession, Organization
from accounts.services.account_deletion_service import deactivate_user_account


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'is_active', 'created_at', 'doctor_count']
    list_filter = ['is_active', 'city']
    search_fields = ['name', 'city', 'address']
    ordering = ['name']

    @admin.display(description='Врачей')
    def doctor_count(self, obj):
        return obj.doctors.count()


class DoctorProfileInline(admin.StackedInline):
    model = DoctorProfile
    can_delete = False
    verbose_name_plural = 'Профиль доктора'
    fields = ['specialty', 'position', 'workplace', 'city', 'area_of_interest', 'organization']
    raw_id_fields = ['organization']


class PatientProfileInline(admin.StackedInline):
    model = PatientProfile
    can_delete = False
    verbose_name_plural = 'Профиль пациента'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'get_full_name', 'user_type', 'is_email_verified', 'is_staff', 'is_active']
    list_filter = ['user_type', 'is_email_verified', 'is_staff', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'middle_name']
    ordering = ['-date_joined']
    actions = ['deactivate_accounts_action']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'middle_name', 'last_name')}),
        ('Тип пользователя', {'fields': ('user_type', 'is_email_verified', 'can_manage_news')}),
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
        if obj is None:
            return []
        if obj.user_type == 'doctor':
            return [DoctorProfileInline(self.model, self.admin_site)]
        elif obj.user_type == 'patient':
            return [PatientProfileInline(self.model, self.admin_site)]
        return []

    @admin.action(description='Удалить аккаунт пользователя (деактивация + архивирование)')
    def deactivate_accounts_action(self, request, queryset):
        protected = queryset.filter(is_superuser=True)
        if protected.exists():
            self.message_user(
                request,
                f'Невозможно удалить суперпользователей: '
                f'{", ".join(u.email for u in protected)}',
                level=messages.ERROR,
            )
            queryset = queryset.filter(is_superuser=False)

        if not queryset.exists():
            return

        already_deactivated = queryset.filter(is_active=False)
        active_qs = queryset.filter(is_active=True)

        if 'confirm' in request.POST:
            deleted_emails = []
            for user in active_qs:
                try:
                    email = deactivate_user_account(user)
                    deleted_emails.append(email)
                except Exception as exc:
                    self.message_user(
                        request,
                        f'Ошибка при удалении пользователя pk={user.pk}: {exc}',
                        level=messages.ERROR,
                    )

            if deleted_emails:
                self.message_user(
                    request,
                    f'Аккаунты удалены ({len(deleted_emails)}): {", ".join(deleted_emails)}',
                )
            if already_deactivated.exists():
                self.message_user(
                    request,
                    f'Уже были деактивированы ({already_deactivated.count()}) — пропущены.',
                    level=messages.WARNING,
                )
            return

        context = {
            **self.admin_site.each_context(request),
            'title': 'Подтверждение удаления аккаунтов',
            'active_qs': active_qs,
            'already_deactivated': already_deactivated,
            'queryset': queryset,
            'action': 'deactivate_accounts_action',
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            'media': self.media,
        }
        return TemplateResponse(
            request,
            'admin/accounts/user/deactivate_confirm.html',
            context,
        )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'purpose', 'is_used', 'expires_at', 'created_at']
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['user', 'code_hash', 'purpose', 'is_used', 'expires_at', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'short_user_agent', 'created_at', 'last_activity']
    list_filter = ['created_at']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['user', 'session_key', 'ip_address', 'user_agent', 'created_at', 'last_activity']
    ordering = ['-last_activity']
    actions = ['terminate_sessions']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Браузер / устройство')
    def short_user_agent(self, obj):
        return obj.user_agent[:80] + '…' if len(obj.user_agent) > 80 else obj.user_agent

    @admin.action(description='Завершить выбранные сессии')
    def terminate_sessions(self, request, queryset):
        count = queryset.count()
        for session in queryset:
            session.terminate()
        self.message_user(request, f'Завершено сессий: {count}')
