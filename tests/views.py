import json


class _SessionCompleted(Exception):
    def __init__(self, session_id):
        self.session_id = session_id


import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.mixins import DoctorRequiredMixin
from patients.models import Patient
from tests.models import Answer, QuestionOption, ScoreRange, Stage, Test, TestResult, TestSession


# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def _build_sidebar(test, current_order):
    """Формирует список шагов для сайдбара.
    Возвращает список dict с полями: step, name, description, status (done/active/inactive)."""
    stages = list(Stage.objects.filter(test=test).order_by('order'))
    current_stage = next((s for s in stages if s.order == current_order), None)
    current_sidebar_step = current_stage.sidebar_step if current_stage else 1

    seen = {}
    for s in stages:
        if s.sidebar_step not in seen:
            seen[s.sidebar_step] = {
                'step': s.sidebar_step,
                'name': s.name,
                'description': s.description,
            }

    sidebar = []
    for step_num in sorted(seen.keys()):
        item = seen[step_num].copy()
        if step_num < current_sidebar_step:
            item['status'] = 'done'
        elif step_num == current_sidebar_step:
            item['status'] = 'active'
        else:
            item['status'] = 'inactive'
        sidebar.append(item)

    return sidebar


def _get_next_stage(test, current_order):
    return Stage.objects.filter(test=test, order__gt=current_order).order_by('order').first()


def _authorize_session(request, session):
    """Проверяет, имеет ли текущий пользователь право работать с этой сессией."""
    user = request.user
    if user.user_type == 'patient':
        if session.patient.user != user:
            raise PermissionDenied
    elif user.user_type == 'doctor':
        if session.taken_by != user:
            raise PermissionDenied
    else:
        raise PermissionDenied


def _finalize_session(session):
    """Создаёт TestResult из завершённой сессии, подсчитывает баллы и заключение."""
    total_score = 0

    result = TestResult.objects.create(
        session=session,
        test=session.test,
        patient=session.patient,
        taken_by=session.taken_by,
        status='completed',
        started_at=session.started_at,
        completed_at=session.completed_at,
    )

    for stage in session.test.stages.order_by('order'):
        for question in stage.questions.prefetch_related('options').order_by('order'):
            key = f'q_{question.pk}'
            raw = session.answers_data.get(key)
            if raw is None:
                continue

            answer = Answer.objects.create(result=result, question=question)

            if question.question_type == 'scale':
                val = int(raw)
                answer.scale_value = val
                answer.score = val
                total_score += val

            elif question.question_type == 'single':
                try:
                    option = QuestionOption.objects.get(pk=int(raw))
                    answer.selected_options.add(option)
                    answer.score = option.score
                    total_score += option.score
                except QuestionOption.DoesNotExist:
                    pass

            elif question.question_type == 'multiple':
                ids = raw if isinstance(raw, list) else [raw]
                for opt_id in ids:
                    try:
                        option = QuestionOption.objects.get(pk=int(opt_id))
                        answer.selected_options.add(option)
                        answer.score += option.score
                        total_score += option.score
                    except QuestionOption.DoesNotExist:
                        pass

            answer.save()

    # Ищем подходящий диапазон для заключения
    score_range = ScoreRange.objects.filter(
        test=session.test,
        min_score__lte=total_score,
        max_score__gte=total_score,
    ).first()

    result.total_score = total_score
    if score_range:
        result.conclusion_label = score_range.label
        result.conclusion_text = score_range.conclusion
    result.save()

    return result


# ─────────────────────────────────────────────
# Запуск теста — пациент (сам за себя)
# ─────────────────────────────────────────────

class PatientStartTestView(LoginRequiredMixin, View):
    """Пациент нажимает «Начать тестирование» — создаём или возобновляем сессию."""

    def post(self, request, pk):
        if request.user.user_type != 'patient':
            raise PermissionDenied

        test = get_object_or_404(Test, pk=pk, is_active=True)

        try:
            patient = request.user.patient_record
        except Exception:
            raise PermissionDenied

        # Если есть незавершённая сессия — возобновляем
        existing = TestSession.objects.filter(
            test=test,
            patient=patient,
            taken_by=request.user,
            status='in_progress',
        ).order_by('-started_at').first()

        if existing:
            return redirect('tests:stage', session_id=existing.pk, order=existing.current_stage_order)

        session = TestSession.objects.create(
            test=test,
            patient=patient,
            taken_by=request.user,
        )
        first_stage = Stage.objects.filter(test=test).order_by('order').first()
        order = first_stage.order if first_stage else 1
        return redirect('tests:stage', session_id=session.pk, order=order)


# ─────────────────────────────────────────────
# Запуск теста — доктор за пациента
# ─────────────────────────────────────────────

class DoctorStartTestView(DoctorRequiredMixin, View):
    """Доктор запускает тест за пациента из карточки пациента."""

    def post(self, request, pk, patient_id):
        test = get_object_or_404(Test, pk=pk, is_active=True)
        patient = get_object_or_404(Patient, pk=patient_id, assigned_doctor=request.user)

        # Доктор всегда создаёт новую сессию (не возобновляет чужую)
        session = TestSession.objects.create(
            test=test,
            patient=patient,
            taken_by=request.user,
        )
        first_stage = Stage.objects.filter(test=test).order_by('order').first()
        order = first_stage.order if first_stage else 1
        return redirect('tests:stage', session_id=session.pk, order=order)


# ─────────────────────────────────────────────
# Прохождение этапа
# ─────────────────────────────────────────────

class StageView(LoginRequiredMixin, View):
    """GET — показывает этап. POST — сохраняет ответы и переходит дальше."""

    def _get_stage_and_session(self, request, session_id, order):
        session = get_object_or_404(TestSession, pk=session_id)
        # Если сессия уже завершена — редирект на результат
        if session.status == 'completed':
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            raise _SessionCompleted(str(session_id))
        _authorize_session(request, session)
        stage = get_object_or_404(Stage, test=session.test, order=order)
        return session, stage

    def get(self, request, session_id, order):
        try:
            session, stage = self._get_stage_and_session(request, session_id, order)
        except _SessionCompleted as e:
            return redirect('tests:result', session_id=e.session_id)

        questions = list(stage.questions.prefetch_related('options').order_by('order'))
        is_scale_stage = questions and questions[0].question_type == 'scale'

        # Предзаполненные ответы из сохранённого прогресса
        saved_answers = session.answers_data

        # Для шкалы — преобразуем saved answer в int
        scale_saved_value = None
        if is_scale_stage and questions:
            key = f'q_{questions[0].pk}'
            if key in saved_answers:
                scale_saved_value = int(saved_answers[key])

        next_stage = _get_next_stage(session.test, order)
        is_last_stage = next_stage is None

        return render(request, 'tests/session_stage.html', {
            'session': session,
            'stage': stage,
            'questions': questions,
            'saved_answers': saved_answers,
            'sidebar_steps': _build_sidebar(session.test, order),
            'is_scale_stage': is_scale_stage,
            'scale_saved_value': scale_saved_value,
            'is_last_stage': is_last_stage,
            'patient': session.patient,
        })

    def post(self, request, session_id, order):
        try:
            session, stage = self._get_stage_and_session(request, session_id, order)
        except _SessionCompleted as e:
            return redirect('tests:result', session_id=e.session_id)
        questions = stage.questions.order_by('order')

        answers_data = dict(session.answers_data)

        for question in questions:
            key = f'q_{question.pk}'
            if question.question_type == 'scale':
                val = request.POST.get(key)
                if val is not None:
                    answers_data[key] = int(val)
            elif question.question_type == 'single':
                val = request.POST.get(key)
                if val:
                    answers_data[key] = int(val)
            elif question.question_type == 'multiple':
                vals = request.POST.getlist(key)
                answers_data[key] = [int(v) for v in vals if v]

        next_stage = _get_next_stage(session.test, order)

        if next_stage:
            session.answers_data = answers_data
            session.current_stage_order = next_stage.order
            session.save()
            return redirect('tests:stage', session_id=session_id, order=next_stage.order)
        else:
            # Последний этап — завершаем сессию
            session.answers_data = answers_data
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            _finalize_session(session)
            # Редирект: доктор → карточка пациента, пациент → своя карточка
            patient = session.patient
            return redirect('patients:detail', pk=patient.pk)


# ─────────────────────────────────────────────
# AJAX: сохранение прогресса
# ─────────────────────────────────────────────

class SaveProgressView(LoginRequiredMixin, View):
    """AJAX-endpoint: сохраняет текущие ответы без перехода на следующий этап."""

    def post(self, request, session_id):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Неверный формат'}, status=400)

        session = get_object_or_404(TestSession, pk=session_id, status='in_progress')
        try:
            _authorize_session(request, session)
        except PermissionDenied:
            return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)

        answers = dict(session.answers_data)
        answers.update(data.get('answers', {}))
        session.answers_data = answers
        session.save(update_fields=['answers_data'])

        return JsonResponse({'ok': True})


# ─────────────────────────────────────────────
# Страница результатов
# ─────────────────────────────────────────────

class ResultView(LoginRequiredMixin, View):
    """Показывает итоговый результат завершённой сессии."""

    def get(self, request, session_id):
        session = get_object_or_404(TestSession, pk=session_id, status='completed')

        user = request.user
        if user.user_type == 'patient':
            if session.patient.user != user:
                raise PermissionDenied
        elif user.user_type == 'doctor':
            if session.taken_by != user and session.patient.assigned_doctor != user:
                raise PermissionDenied
        else:
            raise PermissionDenied

        result = get_object_or_404(TestResult, session=session)
        answers = list(
            result.answers
            .select_related('question', 'question__stage')
            .prefetch_related('selected_options')
            .order_by('question__stage__order', 'question__order')
        )

        # Подсчёт баллов по каждому шагу сайдбара
        step_scores = {}   # sidebar_step -> {'score': int, 'name': str}
        step_stages = {}   # sidebar_step -> stage (для имени)
        for answer in answers:
            stage = answer.question.stage
            step = stage.sidebar_step
            if step not in step_scores:
                step_scores[step] = 0
                step_stages[step] = stage
            step_scores[step] += answer.score

        # Заключение для каждого шага
        sub_results = []
        for step in sorted(step_scores.keys()):
            score = step_scores[step]
            stage = step_stages[step]
            score_range = ScoreRange.objects.filter(
                test=session.test,
                sidebar_step=step,
                min_score__lte=score,
                max_score__gte=score,
            ).first()
            sub_results.append({
                'name': stage.name,
                'score': score,
                'label': score_range.label if score_range else '—',
                'conclusion': score_range.conclusion if score_range else '',
            })

        return render(request, 'tests/session_result.html', {
            'session': session,
            'result': result,
            'answers': answers,
            'patient': session.patient,
            'sub_results': sub_results,
        })


# ─────────────────────────────────────────────
# Доктор: управление тестами
# ─────────────────────────────────────────────

from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from tests.models import Question


class MyResultsView(LoginRequiredMixin, View):
    """История завершённых тестов пациента — редирект на его карточку."""

    def get(self, request):
        try:
            patient = request.user.patient_record
            from django.shortcuts import redirect as _redirect
            return _redirect('patients:detail', pk=patient.pk)
        except Exception:
            return redirect('core:dashboard')


class TestManageListView(DoctorRequiredMixin, ListView):
    model = Test
    template_name = 'tests/test_manage_list.html'
    context_object_name = 'tests'
    paginate_by = 20

    def get_queryset(self):
        return Test.objects.all().select_related('created_by')


class TestCreateView(DoctorRequiredMixin, CreateView):
    model = Test
    template_name = 'tests/test_form.html'
    fields = ['title', 'description', 'is_active']
    success_url = reverse_lazy('tests:manage')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TestUpdateView(DoctorRequiredMixin, UpdateView):
    model = Test
    template_name = 'tests/test_form.html'
    fields = ['title', 'description', 'is_active']
    success_url = reverse_lazy('tests:manage')


class TestDeleteView(DoctorRequiredMixin, DeleteView):
    model = Test
    template_name = 'tests/test_confirm_delete.html'
    success_url = reverse_lazy('tests:manage')
    context_object_name = 'test'


class AllResultsView(DoctorRequiredMixin, ListView):
    model = TestResult
    template_name = 'tests/all_results.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        return TestResult.objects.filter(
            patient__assigned_doctor=self.request.user,
        ).select_related('test', 'patient__user', 'taken_by').order_by('-completed_at')
