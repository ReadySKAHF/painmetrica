import json
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from accounts.mixins import DoctorRequiredMixin
from patients.models import Patient


class PatientListView(DoctorRequiredMixin, ListView):
    """Список пациентов доктора"""

    model = Patient
    template_name = 'patients/patient_list.html'
    context_object_name = 'patients'
    paginate_by = 20

    def get_queryset(self):
        # Показываем только пациентов текущего доктора
        return Patient.objects.filter(assigned_doctor=self.request.user).select_related('user')


class PatientDetailView(LoginRequiredMixin, DetailView):
    """Карточка пациента — доступна доктору (свои пациенты) и самому пациенту"""

    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'doctor':
            return Patient.objects.filter(
                assigned_doctor=user
            ).select_related('user', 'user__patient_profile')
        elif user.user_type == 'patient':
            return Patient.objects.filter(
                user=user
            ).select_related('user', 'user__patient_profile')
        return Patient.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        DURATION_LABELS = {
            '1w': 'Менее 1 недели',
            '1m': '1–4 недели',
            '3m': '1–3 месяца',
            '6m': '3–6 месяцев',
            '1y': '6–12 месяцев',
            '1y+': 'Более 1 года',
        }

        from tests.models import ScoreRange

        def build_sub_results(result):
            answers = (
                result.answers
                .select_related('question__stage')
            )
            step_scores = {}
            step_stages = {}
            for answer in answers:
                stage = answer.question.stage
                if stage is None:
                    continue
                step = stage.sidebar_step
                if step not in step_scores:
                    step_scores[step] = 0
                    step_stages[step] = stage
                step_scores[step] += answer.score
            sub_results = []
            for step in sorted(step_scores.keys()):
                score = step_scores[step]
                stage = step_stages[step]
                score_range = ScoreRange.objects.filter(
                    test=result.test,
                    sidebar_step=step,
                    min_score__lte=score,
                    max_score__gte=score,
                ).first()
                sub_results.append({
                    'name': stage.name,
                    'score': score,
                    'label': score_range.label if score_range else '—',
                })
            return sub_results

        raw_results = self.object.test_results.filter(
            status='completed'
        ).select_related('test', 'session').order_by('-completed_at')

        context['results_with_subs'] = [
            {'result': r, 'sub_results': build_sub_results(r)}
            for r in raw_results
        ]
        context['test_results'] = raw_results  # для обратной совместимости
        context['is_doctor'] = self.request.user.user_type == 'doctor'
        context['pain_duration_label'] = DURATION_LABELS.get(
            self.object.pain_duration, '—'
        ) if self.object.pain_duration else '—'
        try:
            context['date_of_birth'] = self.object.user.patient_profile.date_of_birth
        except Exception:
            context['date_of_birth'] = None

        from tests.models import Test
        context['available_tests'] = Test.objects.filter(is_active=True)
        return context


class PatientCreateView(DoctorRequiredMixin, CreateView):
    """Создание нового пациента"""

    model = Patient
    template_name = 'patients/patient_form.html'
    fields = ['user', 'medical_history', 'notes']
    success_url = reverse_lazy('patients:list')

    def form_valid(self, form):
        # Автоматически назначаем текущего доктора
        form.instance.assigned_doctor = self.request.user
        messages.success(self.request, 'Пациент успешно добавлен.')
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Ограничиваем выбор только пользователями-пациентами без назначенного доктора
        from django.contrib.auth import get_user_model
        User = get_user_model()
        form.fields['user'].queryset = User.objects.filter(
            user_type='patient',
            patient_record__assigned_doctor__isnull=True
        )
        return form


class PatientUpdateView(DoctorRequiredMixin, UpdateView):
    """Редактирование пациента"""

    model = Patient
    template_name = 'patients/patient_form.html'
    fields = ['medical_history', 'notes']
    success_url = reverse_lazy('patients:list')

    def get_queryset(self):
        # Редактировать только своих пациентов
        return Patient.objects.filter(assigned_doctor=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Данные пациента обновлены.')
        return super().form_valid(form)


class PatientDeleteView(DoctorRequiredMixin, DeleteView):
    """Удаление пациента"""

    model = Patient
    template_name = 'patients/patient_confirm_delete.html'
    success_url = reverse_lazy('patients:list')
    context_object_name = 'patient'

    def get_queryset(self):
        # Удалять только своих пациентов
        return Patient.objects.filter(assigned_doctor=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Пациент успешно удален.')
        return super().delete(request, *args, **kwargs)


class PatientUpdateAPIView(LoginRequiredMixin, View):
    """AJAX: обновить данные пациента (доктор или сам пациент)"""

    DURATION_LABELS = {
        '1w': 'Менее 1 недели',
        '1m': '1–4 недели',
        '3m': '1–3 месяца',
        '6m': '3–6 месяцев',
        '1y': '6–12 месяцев',
        '1y+': 'Более 1 года',
    }

    def post(self, request, pk):
        user = request.user
        try:
            if user.user_type == 'doctor':
                patient = Patient.objects.select_related(
                    'user', 'user__patient_profile'
                ).get(pk=pk, assigned_doctor=user)
            elif user.user_type == 'patient':
                patient = Patient.objects.select_related(
                    'user', 'user__patient_profile'
                ).get(pk=pk, user=user)
            else:
                return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)
        except Patient.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Пациент не найден'}, status=404)

        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        if not first_name or not last_name:
            return JsonResponse({'success': False, 'error': 'Имя и фамилия обязательны'}, status=400)

        patient_user = patient.user
        patient_user.first_name = first_name
        patient_user.middle_name = data.get('middle_name', '').strip()
        patient_user.last_name = last_name
        patient_user.save(update_fields=['first_name', 'middle_name', 'last_name'])

        # Обновляем дату рождения
        dob_str = data.get('date_of_birth', '').strip()
        try:
            profile = patient_user.patient_profile
        except Exception:
            from accounts.models import PatientProfile
            profile = PatientProfile.objects.create(user=patient_user)

        if dob_str:
            try:
                profile.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Неверный формат даты'}, status=400)
        else:
            profile.date_of_birth = None
        profile.save(update_fields=['date_of_birth'])

        # Доктор может обновлять медицинские поля
        if user.user_type == 'doctor':
            patient.pain_location = data.get('pain_location', '').strip()
            duration = data.get('pain_duration', '').strip()
            valid_durations = ['', '1w', '1m', '3m', '6m', '1y', '1y+']
            patient.pain_duration = duration if duration in valid_durations else ''
            patient.save(update_fields=['pain_location', 'pain_duration'])

        return JsonResponse({
            'success': True,
            'full_name': patient_user.get_full_name(),
            'date_of_birth': profile.date_of_birth.strftime('%d.%m.%Y') if profile.date_of_birth else '',
            'date_of_birth_iso': profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else '',
            'pain_location': patient.pain_location,
            'pain_duration': patient.pain_duration,
            'pain_duration_label': (
                self.DURATION_LABELS.get(patient.pain_duration, '—')
                if patient.pain_duration else '—'
            ),
        })


class PatientMyProfileView(LoginRequiredMixin, View):
    """Редирект пациента на его собственную карточку."""

    def get(self, request):
        try:
            patient = request.user.patient_record
            return redirect('patients:detail', pk=patient.pk)
        except Exception:
            return redirect('core:dashboard')
