from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from accounts.services.email_service import send_email
from django.urls import reverse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from accounts.forms import (
    RegisterStepOneForm,
    DoctorProfileForm,
    OTPVerificationForm,
    LoginForm,
    PatientManualCreateForm,
    PatientRegisterViaInviteForm,
    PasswordResetRequestForm,
    PasswordResetSetForm,
)
from accounts.models import DoctorProfile, PatientProfile
from accounts.services.otp_service import OTPService
from patients.models import Patient


class RegisterStepOneView(View):
    """Шаг 1: Регистрация - личные данные"""

    template_name = 'accounts/register_step1.html'

    def get(self, request):
        # Если уже авторизован - перенаправить
        if request.user.is_authenticated:
            return redirect('core:dashboard')

        # Подставляем ранее введённые данные при возврате с шага 2
        initial = {}
        if 'registration_data' in request.session:
            d = request.session['registration_data']
            initial = {
                'first_name':  d.get('first_name', ''),
                'middle_name': d.get('middle_name', ''),
                'last_name':   d.get('last_name', ''),
                'email':       d.get('email', ''),
            }

        form = RegisterStepOneForm(initial=initial)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegisterStepOneForm(request.POST)

        if form.is_valid():
            # Сохраняем данные в сессию (регистрация только для докторов)
            request.session['registration_data'] = {
                'first_name': form.cleaned_data['first_name'],
                'middle_name': form.cleaned_data['middle_name'],
                'last_name': form.cleaned_data['last_name'],
                'email': form.cleaned_data['email'],
                'user_type': 'doctor',
                'password': form.cleaned_data['password'],
            }

            # Переход на второй шаг (профессиональные данные доктора)
            return redirect('accounts:register_step_two')

        return render(request, self.template_name, {'form': form})

    def _create_user_and_profile(self, data, doctor_profile_data=None):
        """Создание пользователя и профиля"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Создаем пользователя
        user = User.objects.create_user(
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            middle_name=data['middle_name'],
            last_name=data['last_name'],
            user_type=data['user_type'],
            is_email_verified=False
        )

        # Создаем профиль в зависимости от типа
        if user.user_type == 'doctor' and doctor_profile_data:
            DoctorProfile.objects.create(user=user, **doctor_profile_data)
        elif user.user_type == 'patient':
            PatientProfile.objects.create(user=user)
            # Создаем запись пациента для управления докторами
            Patient.objects.create(user=user)

        return user


class RegisterStepTwoView(View):
    """Шаг 2: Регистрация - профессиональные данные (только для докторов)"""

    template_name = 'accounts/register_step2.html'

    def get(self, request):
        # Проверяем наличие данных первого шага
        if 'registration_data' not in request.session:
            messages.error(request, 'Сначала заполните первый шаг регистрации.')
            return redirect('accounts:register_step_one')

        # Проверка что это доктор
        if request.session['registration_data'].get('user_type') != 'doctor':
            return redirect('accounts:register_verify')

        # Подставляем ранее введённые данные при возврате с шага 3
        step2_data = request.session.get('registration_step2_data', {})
        form = DoctorProfileForm(initial=step2_data)
        return render(request, self.template_name, {'form': form, 'step2_data': step2_data})

    def post(self, request):
        # Проверяем наличие данных первого шага
        if 'registration_data' not in request.session:
            messages.error(request, 'Сначала заполните первый шаг регистрации.')
            return redirect('accounts:register_step_one')

        form = DoctorProfileForm(request.POST)

        if form.is_valid():
            # Сохраняем данные шага 2 в сессию (пользователь создаётся только на шаге 4)
            request.session['registration_step2_data'] = {
                'specialty':        form.cleaned_data.get('specialty', ''),
                'position':         form.cleaned_data.get('position', ''),
                'workplace':        form.cleaned_data.get('workplace', ''),
                'city':             form.cleaned_data.get('city', ''),
                'area_of_interest': form.cleaned_data.get('area_of_interest', ''),
            }

            return redirect('accounts:register_step_three')

        return render(request, self.template_name, {'form': form})


class RegisterStepThreeView(View):
    """Шаг 3: Ознакомление с пользовательским соглашением"""

    template_name = 'accounts/register_step3.html'

    def get(self, request):
        if 'registration_step2_data' not in request.session:
            return redirect('accounts:register_step_one')
        agreed = request.session.get('step3_agreed', False)
        return render(request, self.template_name, {'agreed': agreed})

    def post(self, request):
        if 'registration_step2_data' not in request.session:
            return redirect('accounts:register_step_one')
        request.session['step3_agreed'] = True
        return redirect('accounts:register_step_four')


class RegisterStepFourView(View):
    """Шаг 4: Ознакомление с политикой обработки персональных данных"""

    template_name = 'accounts/register_step4.html'

    def get(self, request):
        if 'registration_step2_data' not in request.session:
            return redirect('accounts:register_step_one')
        return render(request, self.template_name)

    def post(self, request):
        if 'registration_step2_data' not in request.session or 'registration_data' not in request.session:
            return redirect('accounts:register_step_one')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Удаляем незавершённую регистрацию с тем же email (если вдруг есть)
        email = request.session['registration_data']['email']
        User.objects.filter(email__iexact=email, is_email_verified=False).delete()

        # Создаём пользователя с профилем доктора только после принятия обеих политик
        user = RegisterStepOneView()._create_user_and_profile(
            request.session['registration_data'],
            doctor_profile_data=request.session['registration_step2_data'],
        )

        request.session['registration_user_id'] = user.id

        # Отправляем OTP
        OTPService.generate_and_send_otp(user, purpose='registration')
        messages.success(request, 'Код подтверждения отправлен на ваш email.')
        return redirect('accounts:register_verify')


class RegisterVerifyOTPView(View):
    """Шаг 3: Верификация OTP кода при регистрации"""

    template_name = 'accounts/register_verify.html'

    def get(self, request):
        # Проверяем наличие ID пользователя
        if 'registration_user_id' not in request.session:
            messages.error(request, 'Сначала завершите регистрацию.')
            return redirect('accounts:register_step_one')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=request.session['registration_user_id'])
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден.')
            return redirect('accounts:register_step_one')

        form = OTPVerificationForm()
        return render(request, self.template_name, {'form': form, 'user': user})

    def post(self, request):
        if 'registration_user_id' not in request.session:
            messages.error(request, 'Сначала завершите регистрацию.')
            return redirect('accounts:register_step_one')

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=request.session['registration_user_id'])
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден.')
            return redirect('accounts:register_step_one')

        form = OTPVerificationForm(request.POST)

        if form.is_valid():
            # Проверяем OTP
            success, error = OTPService.verify_otp(
                user,
                form.cleaned_data['otp_code'],
                purpose='registration'
            )

            if success:
                # Помечаем email как подтвержденный
                user.is_email_verified = True
                user.save()

                # Очищаем сессию
                request.session.pop('registration_data', None)
                request.session.pop('registration_user_id', None)

                # Устанавливаем бэкенд для аутентификации
                user.backend = 'accounts.backends.EmailBackend'

                # Авторизуем пользователя
                login(request, user)

                messages.success(request, 'Регистрация успешно завершена!')
                return redirect('core:dashboard')
            else:
                messages.error(request, error)

        return render(request, self.template_name, {'form': form, 'user': user})


class LoginView(View):
    """Экран 1: Вход - email и пароль"""

    template_name = 'accounts/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')

        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            # Аутентификация
            user = authenticate(request, email=email, password=password)

            if user is not None:
                # Отправляем OTP для второго фактора
                OTPService.generate_and_send_otp(user, purpose='login')

                # Сохраняем ID пользователя в сессии
                request.session['login_user_id'] = user.id

                messages.success(request, 'Код подтверждения отправлен на ваш email.')
                return redirect('accounts:login_verify')
            else:
                messages.error(request, 'Неверный email или пароль.')

        return render(request, self.template_name, {'form': form})


class LoginVerifyOTPView(View):
    """Экран 2: Вход - проверка OTP кода"""

    template_name = 'accounts/login_verify.html'

    def _get_otp_user(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(id=request.session['login_user_id'])
        except User.DoesNotExist:
            return None

    def get(self, request):
        if 'login_user_id' not in request.session:
            messages.error(request, 'Сначала введите email и пароль.')
            return redirect('accounts:login')

        otp_user = self._get_otp_user(request)
        form = OTPVerificationForm()
        return render(request, self.template_name, {'form': form, 'otp_user': otp_user})

    def post(self, request):
        if 'login_user_id' not in request.session:
            messages.error(request, 'Сначала введите email и пароль.')
            return redirect('accounts:login')

        otp_user = self._get_otp_user(request)
        form = OTPVerificationForm(request.POST)

        if form.is_valid():
            if otp_user is None:
                messages.error(request, 'Пользователь не найден.')
                return redirect('accounts:login')

            # Проверяем OTP
            success, error = OTPService.verify_otp(
                otp_user,
                form.cleaned_data['otp_code'],
                purpose='login'
            )

            if success:
                # Очищаем сессию
                request.session.pop('login_user_id', None)

                # Устанавливаем бэкенд для аутентификации
                otp_user.backend = 'accounts.backends.EmailBackend'

                # Авторизуем пользователя
                login(request, otp_user)

                messages.success(request, f'Добро пожаловать, {otp_user.first_name}!')
                return redirect('core:dashboard')
            else:
                messages.error(request, error)

        return render(request, self.template_name, {'form': form, 'otp_user': otp_user})


class LogoutView(View):
    """Выход из системы"""

    def get(self, request):
        logout(request)
        messages.success(request, 'Вы успешно вышли из системы.')
        return redirect('core:home')


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class ResendOTPView(View):
    """API для повторной отправки OTP кода"""

    def post(self, request):
        # Определяем, откуда запрос - регистрация или вход
        user_id = (
            request.session.get('registration_user_id')
            or request.session.get('login_user_id')
            or request.session.get('patient_invite_user_id')
        )
        if 'registration_user_id' in request.session:
            purpose = 'registration'
        elif 'patient_invite_user_id' in request.session:
            purpose = 'registration'
        else:
            purpose = 'login'

        if not user_id:
            return JsonResponse({'success': False, 'message': 'Сессия истекла.'}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
            OTPService.generate_and_send_otp(user, purpose)

            return JsonResponse({
                'success': True,
                'message': 'Новый код отправлен на ваш email.'
            })

        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Пользователь не найден.'}, status=404)


@method_decorator(ratelimit(key='ip', rate='10/m', method='GET', block=True), name='get')
class CheckEmailView(View):
    """AJAX: проверка существования email в системе"""

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        email = request.GET.get('email', '').strip().lower()
        if not email:
            return JsonResponse({'exists': False})
        exists = User.objects.filter(email__iexact=email).exists()
        return JsonResponse({'exists': exists})


# ──────────────────────────────────────────────────────────────────────
#  РЕГИСТРАЦИЯ ПАЦИЕНТОВ
# ──────────────────────────────────────────────────────────────────────

class SendPatientInvitationView(LoginRequiredMixin, View):
    """AJAX: отправить ссылку-приглашение пациенту на email"""

    def post(self, request):
        if request.user.user_type != 'doctor':
            return JsonResponse({'success': False, 'message': 'Нет доступа.'}, status=403)

        email = request.POST.get('email', '').strip().lower()

        if not email:
            return JsonResponse({'success': False, 'message': 'Email не указан.'})

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({'success': False, 'message': 'Некорректный адрес электронной почты'})

        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'success': False, 'message': 'Пользователь с таким email уже зарегистрирован.'})

        from accounts.models import PatientInvitation
        invitation = PatientInvitation.objects.create(doctor=request.user, email=email)

        invite_url = request.build_absolute_uri(
            reverse('accounts:patient_register_invite', kwargs={'token': invitation.token})
        )

        subject = 'Приглашение на регистрацию в Painmetrica'
        message = (
            f'Здравствуйте!\n\n'
            f'Врач {request.user.get_full_name()} приглашает вас зарегистрироваться '
            f'в системе Painmetrica.\n\n'
            f'Для регистрации перейдите по ссылке:\n{invite_url}\n\n'
            f'Ссылка действительна в течение 7 дней.\n\n'
            f'-- Система Painmetrica'
        )

        try:
            send_email(to=email, subject=subject, text=message)
        except Exception:
            invitation.delete()
            return JsonResponse({'success': False, 'message': 'Ошибка отправки письма. Проверьте email и попробуйте снова.'})

        return JsonResponse({'success': True})


class ManualPatientCreateView(LoginRequiredMixin, View):
    """AJAX: доктор вручную создаёт аккаунт пациента"""

    def post(self, request):
        if request.user.user_type != 'doctor':
            return JsonResponse({'success': False, 'message': 'Нет доступа.'}, status=403)

        form = PatientManualCreateForm(request.POST)

        if form.is_valid():
            import uuid as _uuid
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Генерируем внутренний email — пациент не сможет войти
            internal_email = f"patient_{_uuid.uuid4().hex}@nologin.internal"

            user = User.objects.create_user(
                email=internal_email,
                password=None,  # unusable password — вход невозможен
                first_name=form.cleaned_data['first_name'],
                middle_name=form.cleaned_data.get('middle_name', ''),
                last_name=form.cleaned_data['last_name'],
                user_type='patient',
                is_email_verified=False,
            )
            PatientProfile.objects.create(
                user=user,
                date_of_birth=form.cleaned_data.get('date_of_birth'),
            )
            Patient.objects.create(
                user=user,
                assigned_doctor=request.user,
                medical_history=form.cleaned_data.get('diagnosis', ''),
                pain_location=form.cleaned_data.get('pain_location', ''),
                pain_duration=form.cleaned_data.get('pain_duration', ''),
            )

            return JsonResponse({'success': True, 'patient_name': user.get_full_name()})

        errors = {field: errs[0] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors})


class PatientRegisterViaInviteStep1View(View):
    """Шаг 1: пациент заполняет данные по ссылке-приглашению"""

    template_name = 'accounts/patient_register_invite.html'

    def _get_invitation(self, token):
        from accounts.models import PatientInvitation
        try:
            return PatientInvitation.objects.select_related('doctor').get(token=token)
        except PatientInvitation.DoesNotExist:
            return None

    def get(self, request, token):
        invitation = self._get_invitation(token)
        if not invitation or not invitation.is_valid():
            return render(request, 'accounts/patient_invite_invalid.html')

        initial = {}
        if 'patient_invite_user_id' in request.session:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                existing = User.objects.get(id=request.session['patient_invite_user_id'])
                initial = {
                    'first_name': existing.first_name,
                    'last_name': existing.last_name,
                    'middle_name': existing.middle_name,
                }
                if hasattr(existing, 'patient_profile') and existing.patient_profile.date_of_birth:
                    initial['date_of_birth'] = existing.patient_profile.date_of_birth.strftime('%Y-%m-%d')
            except User.DoesNotExist:
                pass

        form = PatientRegisterViaInviteForm(initial=initial)
        return render(request, self.template_name, {'form': form, 'invitation': invitation})

    def post(self, request, token):
        invitation = self._get_invitation(token)
        if not invitation or not invitation.is_valid():
            return render(request, 'accounts/patient_invite_invalid.html')

        form = PatientRegisterViaInviteForm(request.POST)

        if form.is_valid():
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Проверяем, не зарегистрирован ли уже этот email (только верифицированные)
            if User.objects.filter(email__iexact=invitation.email, is_email_verified=True).exists():
                return render(request, 'accounts/patient_invite_invalid.html',
                              {'error': 'Этот email уже зарегистрирован в системе.'})

            # Удаляем незавершённую регистрацию с тем же email (если есть)
            User.objects.filter(email__iexact=invitation.email, is_email_verified=False).delete()

            user = User.objects.create_user(
                email=invitation.email,
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                middle_name=form.cleaned_data.get('middle_name', ''),
                last_name=form.cleaned_data['last_name'],
                user_type='patient',
                is_email_verified=False,
            )
            PatientProfile.objects.create(
                user=user,
                date_of_birth=form.cleaned_data.get('date_of_birth'),
            )
            Patient.objects.create(user=user, assigned_doctor=invitation.doctor)

            request.session['patient_invite_user_id'] = user.id
            request.session['patient_invite_token'] = str(token)

            return redirect('accounts:patient_register_agreement')

        return render(request, self.template_name, {'form': form, 'invitation': invitation})


class PatientRegisterAgreementView(View):
    """Шаг 2: пациент читает пользовательское соглашение"""

    template_name = 'accounts/patient_register_invite_agreement.html'

    def get(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')
        back_token = request.session.get('patient_invite_token')
        return render(request, self.template_name, {'back_token': back_token})

    def post(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')
        if request.POST.get('agreed'):
            return redirect('accounts:patient_register_policy')
        back_token = request.session.get('patient_invite_token')
        return render(request, self.template_name, {'agreed': False, 'back_token': back_token})


class PatientRegisterPolicyView(View):
    """Шаг 3: пациент читает политику обработки персональных данных"""

    template_name = 'accounts/patient_register_invite_policy.html'

    def get(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')
        return render(request, self.template_name)

    def post(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=request.session['patient_invite_user_id'])
        except User.DoesNotExist:
            return redirect('core:home')

        if request.POST.get('agreed'):
            OTPService.generate_and_send_otp(user, purpose='registration')
            return redirect('accounts:patient_register_invite_verify')
        return render(request, self.template_name, {'agreed': False})


class PatientRegisterViaInviteVerifyView(View):
    """Шаг 4: пациент подтверждает email через OTP"""

    template_name = 'accounts/patient_register_invite_verify.html'

    def get(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=request.session['patient_invite_user_id'])
        except User.DoesNotExist:
            return redirect('core:home')

        form = OTPVerificationForm()
        return render(request, self.template_name, {'form': form, 'user': user})

    def post(self, request):
        if 'patient_invite_user_id' not in request.session:
            return redirect('core:home')

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=request.session['patient_invite_user_id'])
        except User.DoesNotExist:
            return redirect('core:home')

        form = OTPVerificationForm(request.POST)

        if form.is_valid():
            success, error = OTPService.verify_otp(
                user, form.cleaned_data['otp_code'], purpose='registration'
            )

            if success:
                user.is_email_verified = True
                user.save()

                # Помечаем приглашение как использованное
                from accounts.models import PatientInvitation
                token = request.session.get('patient_invite_token')
                if token:
                    PatientInvitation.objects.filter(token=token).update(is_used=True)

                # Уведомляем доктора об успешной регистрации пациента
                try:
                    patient_record = Patient.objects.select_related('assigned_doctor').get(user=user)
                    doctor = patient_record.assigned_doctor
                    if doctor and doctor.email:
                        full_name = ' '.join(filter(None, [user.last_name, user.first_name, user.middle_name]))
                        send_email(
                            to=doctor.email,
                            subject='Ваш пациент успешно зарегистрировался в системе',
                            text=(
                                f'Пациент {full_name} успешно зарегистрировался в системе Painmetrika '
                                f'по вашему приглашению.\n\n'
                                f'Обращаем ваше внимание, что для достоверности формирования заключения, '
                                f'вам необходимо указать для вашего пациента следующие данные: '
                                f'"Диагноз", "Длительность боли" и "Локализация боли"\n\n'
                                f'Указать их можно в вашем личном кабинете по следующему пути:\n'
                                f'Вкладка "Мои пациенты" -> Находите вашего пациента и нажимаете на кнопку '
                                f'"Карточка пациента" -> Нажимаете на кнопку "Редактировать" -> '
                                f'В появившихся полях заполняете поля, указанные выше -> '
                                f'Нажимаете на кнопку "Сохранить"'
                            ),
                        )
                except Exception:
                    pass

                request.session.pop('patient_invite_user_id', None)
                request.session.pop('patient_invite_token', None)

                user.backend = 'accounts.backends.EmailBackend'
                login(request, user)

                messages.success(request, f'Добро пожаловать, {user.first_name}! Регистрация завершена.')
                return redirect('core:dashboard')
            else:
                messages.error(request, error)

        return render(request, self.template_name, {'form': form, 'user': user})


# ──────────────────────────────────────────────────────────────────────
#  ВОССТАНОВЛЕНИЕ ПАРОЛЯ
# ──────────────────────────────────────────────────────────────────────

@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class PasswordResetRequestView(View):
    """Страница 1: Ввод email для сброса пароля"""

    template_name = 'accounts/password_reset_request.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            from django.contrib.auth import get_user_model
            User = get_user_model()
            from accounts.models import PasswordResetToken

            email = form.cleaned_data['email']
            user = User.objects.get(email__iexact=email, is_email_verified=True)

            # Инвалидируем старые токены
            PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

            # Создаём новый токен
            token = PasswordResetToken.objects.create(user=user)

            # Формируем ссылку
            reset_url = request.build_absolute_uri(
                reverse('accounts:password_reset_set', kwargs={'token': token.token})
            )

            subject = 'Восстановление пароля от системы Painmetrica'
            message = (
                f'Мы получили запрос на сброс пароля для вашего аккаунта.\n'
                f'Перейдите по этой ссылке для сброса пароля и создания нового: {reset_url}\n\n'
                f'Система Painmetrica'
            )

            try:
                send_email(to=email, subject=subject, text=message)
            except Exception:
                token.delete()
                messages.error(request, 'Ошибка отправки письма. Попробуйте снова.')
                return render(request, self.template_name, {'form': form})

            return render(request, self.template_name, {
                'form': PasswordResetRequestForm(),
                'show_success_modal': True,
            })

        return render(request, self.template_name, {'form': form})


class PasswordResetSetView(View):
    """Страница 2: Ввод нового пароля по токену из письма"""

    template_name = 'accounts/password_reset_set.html'
    invalid_template = 'accounts/password_reset_invalid.html'

    def _get_token(self, token_uuid):
        from accounts.models import PasswordResetToken
        try:
            return PasswordResetToken.objects.select_related('user').get(token=token_uuid)
        except PasswordResetToken.DoesNotExist:
            return None

    def get(self, request, token):
        token_obj = self._get_token(token)
        if not token_obj or not token_obj.is_valid():
            return render(request, self.invalid_template)

        form = PasswordResetSetForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, token):
        token_obj = self._get_token(token)
        if not token_obj or not token_obj.is_valid():
            return render(request, self.invalid_template)

        user = token_obj.user
        form = PasswordResetSetForm(request.POST, user=user)

        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save()

            token_obj.is_used = True
            token_obj.save()

            return render(request, self.template_name, {
                'form': form,
                'show_success_modal': True,
            })

        return render(request, self.template_name, {'form': form})
