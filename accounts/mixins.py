from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from functools import wraps


class DoctorRequiredMixin(LoginRequiredMixin):
    """
    Mixin для проверки, что пользователь является доктором
    Использовать для class-based views
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.user_type != 'doctor':
            raise PermissionDenied('Доступ разрешен только для докторов')

        return super().dispatch(request, *args, **kwargs)


class PatientRequiredMixin(LoginRequiredMixin):
    """
    Mixin для проверки, что пользователь является пациентом
    Использовать для class-based views
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.user_type != 'patient':
            raise PermissionDenied('Доступ разрешен только для пациентов')

        return super().dispatch(request, *args, **kwargs)


# Декораторы для function-based views

def doctor_required(view_func):
    """
    Декоратор для проверки, что пользователь является доктором
    Использовать для function-based views
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        if request.user.user_type != 'doctor':
            raise PermissionDenied('Доступ разрешен только для докторов')

        return view_func(request, *args, **kwargs)
    return wrapper


def patient_required(view_func):
    """
    Декоратор для проверки, что пользователь является пациентом
    Использовать для function-based views
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        if request.user.user_type != 'patient':
            raise PermissionDenied('Доступ разрешен только для пациентов')

        return view_func(request, *args, **kwargs)
    return wrapper
