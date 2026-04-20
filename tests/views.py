import json


class _SessionCompleted(Exception):
    def __init__(self, session_id):
        self.session_id = session_id


from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.mixins import DoctorRequiredMixin
from patients.models import Patient
from tests.models import Answer, Question, QuestionOption, ScoreRange, Stage, Test, TestResult, TestSession


# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def _load_score_ranges(test):
    """Загружает все ScoreRange теста, кэширует на 1 час."""
    key = f'score_ranges:{test.pk}'
    result = cache.get(key)
    if result is None:
        result = list(ScoreRange.objects.filter(test=test))
        cache.set(key, result, 3600)
    return result


def _get_pathotype_label(category, scores_by_step, total_score, conclusion_label):
    """Возвращает строку патотипа по категории теста и баллам по шагам."""
    if category == 'complex':
        dn4  = scores_by_step.get(2, 0)
        csi  = scores_by_step.get(3, 0)
        hads = scores_by_step.get(4, 0)
        if dn4 >= 4 and csi >= 30:
            return 'Смешанный вариант (нейропатический + дисфункциональный)'
        if dn4 >= 4 and csi < 30:
            return 'Преимущественно нейропатический вариант'
        if dn4 < 4 and csi >= 40 and hads >= 8:
            return 'Преимущественно дисфункциональный вариант'
        return 'Преимущественно ноцицептивный вариант'
    if category == 'painad':
        if total_score > 2:
            return 'Ноцицептивный вариант'
        return conclusion_label or '—'
    if category == 'ncsr':
        if total_score > 5:
            return 'Выраженный ноцицептивный ответ.'
        if total_score >= 3:
            return 'Рекомендуется усилить текущую анальгезию'
        return conclusion_label or '—'
    return conclusion_label or '—'


def _match_score_range(ranges, sidebar_step, score):
    """Ищет подходящий диапазон в уже загруженном списке (без запросов к БД)."""
    for sr in ranges:
        if sr.sidebar_step == sidebar_step and sr.min_score <= score <= sr.max_score:
            return sr
    return None


def _build_sidebar(stages, current_order):
    """Формирует список шагов для сайдбара из уже загруженного списка этапов.
    Возвращает список dict с полями: step, name, description, status (done/active/inactive)."""
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
    """Создаёт TestResult из завершённой сессии, подсчитывает баллы и заключение.

    Оптимизация: вместо N SELECT на каждый вариант и N INSERT на каждый ответ
    выполняется 1 SELECT для всех QuestionOption + bulk_create для Answer и M2M.
    Итого: ~5-6 запросов вместо 50+.
    """
    # 1. Собираем все option_id из answers_data одним проходом
    all_option_ids = []
    for key, raw in session.answers_data.items():
        if not key.startswith('q_'):
            continue
        if isinstance(raw, list):
            all_option_ids.extend(int(i) for i in raw if str(i).isdigit())
        elif str(raw).isdigit():
            all_option_ids.append(int(raw))

    # 2. Один SELECT для всех QuestionOption
    options_map = {
        opt.pk: opt
        for opt in QuestionOption.objects.filter(pk__in=all_option_ids)
    }

    result = TestResult.objects.create(
        session=session,
        test=session.test,
        patient=session.patient,
        taken_by=session.taken_by,
        status='completed',
        started_at=session.started_at,
        completed_at=session.completed_at,
    )

    total_score = 0
    answers_to_create = []
    m2m_pairs = []  # (answer_index, option_id)

    # Загружаем все этапы с вопросами за 2 запроса (prefetch)
    stages = session.test.stages.prefetch_related(
        Prefetch('questions', queryset=Question.objects.order_by('order'))
    ).order_by('order')

    for stage in stages:
        for question in stage.questions.all():
            key = f'q_{question.pk}'
            raw = session.answers_data.get(key)
            if raw is None:
                continue

            answer = Answer(result=result, question=question, score=0)

            if question.question_type == 'scale':
                val = int(raw)
                answer.scale_value = val
                answer.score = val
                total_score += val

            elif question.question_type == 'single':
                opt = options_map.get(int(raw)) if str(raw).isdigit() else None
                if opt:
                    answer.score = opt.score
                    total_score += opt.score
                    m2m_pairs.append((len(answers_to_create), opt.pk))

            elif question.question_type == 'multiple':
                ids = raw if isinstance(raw, list) else [raw]
                for opt_id in ids:
                    opt = options_map.get(int(opt_id))
                    if opt:
                        answer.score += opt.score
                        total_score += opt.score
                        m2m_pairs.append((len(answers_to_create), opt.pk))

            answers_to_create.append(answer)

    # Один INSERT вместо N
    created_answers = Answer.objects.bulk_create(answers_to_create)

    # M2M bulk через промежуточную таблицу напрямую
    ThroughModel = Answer.selected_options.through
    ThroughModel.objects.bulk_create([
        ThroughModel(answer_id=created_answers[idx].pk, questionoption_id=opt_id)
        for idx, opt_id in m2m_pairs
    ])

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

        DOCTOR_ONLY = {'Тест PAINAD', 'Тест NCS-R'}
        if test.title in DOCTOR_ONLY:
            raise PermissionDenied

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
        session = get_object_or_404(
            TestSession.objects.select_related('test', 'patient__user', 'taken_by'),
            pk=session_id,
        )
        if session.status == 'completed':
            raise _SessionCompleted(str(session_id))
        _authorize_session(request, session)
        # Структура теста кэшируется: меняется только при редактировании теста через админку
        stages_key = f'test_stages:{session.test_id}'
        all_stages = cache.get(stages_key)
        if all_stages is None:
            all_stages = list(Stage.objects.filter(test=session.test).order_by('order'))
            cache.set(stages_key, all_stages, 3600)
        stage = next((s for s in all_stages if s.order == order), None)
        if stage is None:
            from django.http import Http404
            raise Http404
        return session, stage, all_stages

    def get(self, request, session_id, order):
        try:
            session, stage, all_stages = self._get_stage_and_session(request, session_id, order)
        except _SessionCompleted as e:
            return redirect('tests:result', session_id=e.session_id)

        questions_key = f'stage_questions:{stage.pk}'
        questions = cache.get(questions_key)
        if questions is None:
            questions = list(stage.questions.prefetch_related('options').order_by('order'))
            cache.set(questions_key, questions, 3600)
        is_scale_stage = questions and questions[0].question_type == 'scale'

        # Предзаполненные ответы из сохранённого прогресса
        saved_answers = session.answers_data

        # Для шкалы — преобразуем saved answer в int
        scale_saved_value = None
        if is_scale_stage and questions:
            key = f'q_{questions[0].pk}'
            if key in saved_answers:
                scale_saved_value = int(saved_answers[key])

        # Следующий этап и сайдбар — из уже загруженного списка, без новых запросов
        next_stage = next((s for s in all_stages if s.order > order), None)
        is_last_stage = next_stage is None

        # Смещение для нумерации вопросов в модальном окне валидации:
        # считаем вопросы только в предыдущих этапах с тем же sidebar_step,
        # чтобы нумерация шла в рамках одного теста (например, HADS 1-14, а не 1-54)
        prev_stages_same_step = [
            s for s in all_stages
            if s.order < order and s.sidebar_step == stage.sidebar_step
        ]
        question_offset = 0
        if prev_stages_same_step:
            question_offset = Question.objects.filter(stage__in=prev_stages_same_step).count()

        return render(request, 'tests/session_stage.html', {
            'session': session,
            'stage': stage,
            'questions': questions,
            'saved_answers': saved_answers,
            'sidebar_steps': _build_sidebar(all_stages, order),
            'is_scale_stage': is_scale_stage,
            'scale_saved_value': scale_saved_value,
            'is_last_stage': is_last_stage,
            'patient': session.patient,
            'question_offset': question_offset,
        })

    def post(self, request, session_id, order):
        try:
            session, stage, all_stages = self._get_stage_and_session(request, session_id, order)
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

        next_stage = next((s for s in all_stages if s.order > order), None)

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
            return redirect('tests:result', session_id=session_id)


# ─────────────────────────────────────────────
# AJAX: сохранение прогресса
# ─────────────────────────────────────────────

class SaveProgressView(LoginRequiredMixin, View):
    """AJAX-endpoint: сохраняет текущие ответы без перехода на следующий этап.

    На PostgreSQL: авторизация встроена в WHERE-условие UPDATE — 1 запрос вместо 2.
    На SQLite: классический SELECT + UPDATE (jsonb-оператор недоступен).
    """

    def post(self, request, session_id):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Неверный формат'}, status=400)

        new_answers = data.get('answers', {})
        if not isinstance(new_answers, dict):
            return JsonResponse({'ok': False, 'error': 'Неверный формат'}, status=400)

        if connection.vendor == 'postgresql':
            from django.db.models.expressions import RawSQL

            user = request.user
            if user.user_type == 'patient':
                qs = TestSession.objects.filter(
                    pk=session_id, status='in_progress', patient__user=user
                )
            elif user.user_type == 'doctor':
                qs = TestSession.objects.filter(
                    pk=session_id, status='in_progress', taken_by=user
                )
            else:
                return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)

            updated = qs.update(
                answers_data=RawSQL('answers_data || %s::jsonb', [json.dumps(new_answers)])
            )
            if not updated:
                return JsonResponse({'ok': False, 'error': 'Сессия не найдена'}, status=404)

        else:
            session = get_object_or_404(TestSession, pk=session_id, status='in_progress')
            try:
                _authorize_session(request, session)
            except PermissionDenied:
                return JsonResponse({'ok': False, 'error': 'Нет доступа'}, status=403)

            answers = dict(session.answers_data)
            answers.update(new_answers)
            session.answers_data = answers
            session.save(update_fields=['answers_data'])

        return JsonResponse({'ok': True})


# ─────────────────────────────────────────────
# Страница результатов
# ─────────────────────────────────────────────

class ResultView(LoginRequiredMixin, View):
    """Показывает итоговый результат завершённой сессии."""

    def get(self, request, session_id):
        session = get_object_or_404(
            TestSession.objects.select_related('test', 'patient__user', 'taken_by'),
            pk=session_id, status='completed',
        )

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

        # Заключение для каждого шага — один запрос на все диапазоны
        score_ranges = _load_score_ranges(session.test)
        sub_results = []
        for step in sorted(step_scores.keys()):
            score = step_scores[step]
            stage = step_stages[step]
            score_range = _match_score_range(score_ranges, step, score)
            sub_results.append({
                'sidebar_step': step,
                'name': stage.name,
                'score': score,
                'label': score_range.label if score_range else '—',
                'conclusion': score_range.conclusion if score_range else '',
            })

        category = session.test.category if hasattr(session.test, 'category') else ''
        scores_by_step = {step: step_scores[step] for step in step_scores}
        pathotype_label = _get_pathotype_label(
            category, scores_by_step, result.total_score,
            sub_results[0]['label'] if sub_results else '',
        )
        pathotype_text = ''
        if category == 'ncsr':
            if result.total_score > 5:
                pathotype_text = 'Требуется немедленная коррекция обезболивающей терапии (болюсное введение анальгетика, титрация инфузии) и диагностический поиск причины боли (новое повреждение, осложнение).'
            else:
                pathotype_text = sub_results[0]['conclusion'] if sub_results else ''
        elif sub_results:
            pathotype_text = sub_results[0]['conclusion']

        return render(request, 'tests/session_result.html', {
            'session': session,
            'result': result,
            'answers': answers,
            'patient': session.patient,
            'sub_results': sub_results,
            'pathotype_label': pathotype_label,
            'pathotype_text': pathotype_text,
            'is_doctor': user.user_type == 'doctor',
            'from_detail': request.GET.get('from_detail') == '1',
        })



# ─────────────────────────────────────────────
# Детальные ответы по шагу (sidebar_step)
# ─────────────────────────────────────────────

class ResultDetailView(LoginRequiredMixin, View):
    """Вопросы и ответы по одному sidebar_step."""

    def get(self, request, session_id, sidebar_step):
        session = get_object_or_404(
            TestSession.objects.select_related('test', 'patient__user', 'taken_by'),
            pk=session_id, status='completed',
        )

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
            .filter(question__stage__sidebar_step=sidebar_step)
            .select_related('question', 'question__stage')
            .prefetch_related('selected_options')
            .order_by('question__stage__order', 'question__order')
        )

        return render(request, 'tests/result_detail.html', {
            'session': session,
            'result': result,
            'patient': session.patient,
            'answers': answers,
            'sidebar_step': sidebar_step,
            'from_detail': request.GET.get('from_detail') == '1',
        })


# ─────────────────────────────────────────────
# API: отправка баллов напрямую
# ─────────────────────────────────────────────

class ScoreSubmitAPIView(LoginRequiredMixin, View):
    """POST /api/tests/submit-scores/
    Принимает готовые баллы по шагам (sidebar_step) и возвращает заключения.
    Не создаёт сессию/результат в БД — чистое вычисление.
    Требует: авторизованный пользователь (любой тип).
    """

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Невалидный JSON'}, status=400)

        test_id = data.get('test_id')
        scores  = data.get('scores')  # {sidebar_step: score}

        if not test_id or not isinstance(scores, dict):
            return JsonResponse(
                {'error': 'Обязательные поля: test_id (int), scores (object {step: score})'},
                status=400,
            )

        test = Test.objects.filter(pk=test_id).first()
        if not test:
            return JsonResponse({'error': f'Тест с id={test_id} не найден'}, status=404)

        # Нормализуем ключи к int
        try:
            scores_int = {int(k): int(v) for k, v in scores.items()}
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Ключи и значения scores должны быть числами'}, status=400)

        total_score = sum(scores_int.values())

        results = []
        # Берём уникальные шаги сайдбара из этапов теста
        steps_meta = {}
        for stage in test.stages.order_by('sidebar_step', 'order'):
            if stage.sidebar_step not in steps_meta:
                steps_meta[stage.sidebar_step] = stage.name

        # Один запрос на все диапазоны теста
        score_ranges = _load_score_ranges(test)

        for step in sorted(steps_meta.keys()):
            score = scores_int.get(step)
            if score is None:
                continue

            score_range = _match_score_range(score_ranges, step, score)

            results.append({
                'sidebar_step': step,
                'name': steps_meta[step],
                'score': score,
                'label': score_range.label if score_range else None,
                'conclusion': score_range.conclusion if score_range else None,
            })

        # Общее заключение (диапазон без привязки к шагу)
        overall_range = next(
            (sr for sr in score_ranges
             if sr.sidebar_step is None and sr.min_score <= total_score <= sr.max_score),
            None,
        )

        return JsonResponse({
            'test_id': test.pk,
            'test_title': test.title,
            'total_score': total_score,
            'overall_label': overall_range.label if overall_range else None,
            'overall_conclusion': overall_range.conclusion if overall_range else None,
            'steps': results,
        })


# ─────────────────────────────────────────────
# Доктор: управление тестами
# ─────────────────────────────────────────────



class TestCompareView(DoctorRequiredMixin, View):
    """Сравнение результатов тестов пациента по сопоставимым категориям."""

    COMPARABLE_CATEGORIES = ['complex', 'painad', 'ncsr']

    def get(self, request, patient_pk):
        from datetime import date
        from django.db.models import Prefetch

        patient = get_object_or_404(Patient, pk=patient_pk, assigned_doctor=request.user)

        qs = (
            TestResult.objects
            .filter(
                patient=patient,
                status='completed',
                test__category__in=self.COMPARABLE_CATEGORIES,
            )
            .select_related('test', 'session')
            .prefetch_related(
                # select_related внутри Prefetch: один JOIN-запрос вместо трёх отдельных
                Prefetch(
                    'answers',
                    queryset=Answer.objects.select_related('question__stage')
                    .prefetch_related('selected_options'),
                )
            )
            .order_by('-completed_at')
        )

        # Фильтрация по датам
        date_from_str = request.GET.get('date_from', '').strip()
        date_to_str   = request.GET.get('date_to',   '').strip()
        if date_from_str:
            try:
                qs = qs.filter(completed_at__date__gte=date.fromisoformat(date_from_str))
            except ValueError:
                date_from_str = ''
        if date_to_str:
            try:
                qs = qs.filter(completed_at__date__lte=date.fromisoformat(date_to_str))
            except ValueError:
                date_to_str = ''

        results = list(qs)

        # Один запрос на все ScoreRange для всех тестов
        test_ids = {r.test_id for r in results}
        score_ranges_by_test = {}
        if test_ids:
            for sr in ScoreRange.objects.filter(test_id__in=test_ids):
                score_ranges_by_test.setdefault(sr.test_id, []).append(sr)

        result_groups = [
            {
                'result': r,
                'sub_results': self._build_sub_results(r, score_ranges_by_test.get(r.test_id, [])),
            }
            for r in results
        ]

        context = {
            'patient': patient,
            'result_groups': result_groups,
            'filter_date_from': date_from_str,
            'filter_date_to': date_to_str,
            'is_doctor': True,
        }
        return render(request, 'tests/compare.html', context)

    @staticmethod
    def _build_sub_results(result, score_ranges):
        step_scores = {}
        step_stages = {}
        for answer in result.answers.all():
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
            score_range = _match_score_range(score_ranges, step, score)
            sub_results.append({
                'step': step,
                'name': stage.name,
                'score': score,
                'label': score_range.label if score_range else '—',
                'conclusion': score_range.conclusion if score_range else '',
            })
        return sub_results


class TestMethodologyView(LoginRequiredMixin, View):
    """Страница с методикой расчёта тестов"""

    def get(self, request, *args, **kwargs):
        user = request.user
        context = {'is_doctor': user.user_type == 'doctor', 'is_patient': user.user_type == 'patient'}
        if context['is_patient']:
            try:
                context['patient_pk'] = user.patient_record.pk
            except Exception:
                context['patient_pk'] = None
        return render(request, 'tests/test_methodology.html', context)

