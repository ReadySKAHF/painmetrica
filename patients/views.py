import json
import os
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView

from accounts.mixins import DoctorRequiredMixin
from patients.models import Patient
from tests.views import _load_score_ranges, _match_score_range, _get_pathotype_label



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
        from collections import Counter
        from datetime import date
        from django.db.models import Prefetch
        from tests.models import Answer, ScoreRange, Test, TestSession

        DURATION_LABELS = {
            '1w': 'Менее 1 недели',
            '1m': '1–4 недели',
            '3m': '1–3 месяца',
            '6m': '3–6 месяцев',
            '1y': '6–12 месяцев',
            '1y+': 'Более 1 года',
        }

        # Один запрос: все результаты + все answers с вопросами и этапами
        all_results = list(
            self.object.test_results.filter(status='completed')
            .select_related('test', 'session')
            .prefetch_related(
                Prefetch(
                    'answers',
                    queryset=Answer.objects.select_related('question__stage'),
                )
            )
            .order_by('-completed_at')
        )

        # Один запрос на все ScoreRange для всех тестов из результатов
        test_ids = {r.test_id for r in all_results}
        score_ranges_by_test = {}
        if test_ids:
            for sr in ScoreRange.objects.filter(test_id__in=test_ids):
                score_ranges_by_test.setdefault(sr.test_id, []).append(sr)

        def build_sub_results(result):
            # Использует prefetch-кэш для answers и кэш score_ranges — без запросов к БД
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
            score_ranges = score_ranges_by_test.get(result.test_id, [])
            sub_results = []
            for step in sorted(step_scores.keys()):
                score = step_scores[step]
                stage = step_stages[step]
                score_range = _match_score_range(score_ranges, step, score)
                sub_results.append({
                    'name': stage.name,
                    'score': score,
                    'label': score_range.label if score_range else '—',
                })
            return sub_results

        # Текущий статус — самый последний результат
        current_result = all_results[0] if all_results else None
        if current_result:
            context['current_status'] = {
                'result': current_result,
                'sub_results': build_sub_results(current_result),
            }
            history_list = all_results[1:]
        else:
            context['current_status'] = None
            history_list = all_results

        # Фильтр по датам (в памяти — без лишних запросов)
        date_from_str = self.request.GET.get('date_from', '').strip()
        date_to_str = self.request.GET.get('date_to', '').strip()
        date_from = date_to = None
        if date_from_str:
            try:
                date_from = date.fromisoformat(date_from_str)
            except ValueError:
                date_from_str = ''
        if date_to_str:
            try:
                date_to = date.fromisoformat(date_to_str)
            except ValueError:
                date_to_str = ''
        context['filter_date_from'] = date_from_str
        context['filter_date_to'] = date_to_str

        history_filtered = history_list
        if date_from:
            history_filtered = [r for r in history_filtered if r.completed_at.date() >= date_from]
        if date_to:
            history_filtered = [r for r in history_filtered if r.completed_at.date() <= date_to]

        # Наличие результатов для кнопок скачивания
        context['has_any_results'] = bool(all_results)
        export_list = all_results
        if date_from:
            export_list = [r for r in export_list if r.completed_at.date() >= date_from]
        if date_to:
            export_list = [r for r in export_list if r.completed_at.date() <= date_to]
        context['export_has_results'] = bool(export_list)

        # Пагинация истории (3 на страницу) — paginator работает со списком
        paginator = Paginator(history_filtered, 3)
        history_page = paginator.get_page(self.request.GET.get('page', 1))
        context['history_page'] = history_page
        context['history_results'] = [
            {'result': r, 'sub_results': build_sub_results(r)}
            for r in history_page
        ]

        # Проверяем возможность сравнения: ≥2 завершённых теста одной категории
        COMPARABLE = ['complex', 'painad']
        category_counts = Counter(
            r.test.category
            for r in all_results
            if r.test.category in COMPARABLE
        )
        context['can_compare'] = any(cnt >= 2 for cnt in category_counts.values())

        context['active_tab'] = self.request.GET.get('tab', 'profile')
        context['is_doctor'] = self.request.user.user_type == 'doctor'
        context['pain_duration_label'] = DURATION_LABELS.get(
            self.object.pain_duration, '—'
        ) if self.object.pain_duration else '—'
        try:
            context['date_of_birth'] = self.object.user.patient_profile.date_of_birth
        except Exception:
            context['date_of_birth'] = None

        tests = cache.get('active_tests')
        if tests is None:
            tests = list(Test.objects.filter(is_active=True).order_by('pk'))
            cache.set('active_tests', tests, 3600)
        active_sessions_map = {}
        for session in TestSession.objects.filter(
            patient=self.object,
            status='in_progress',
            taken_by=self.request.user,
        ).order_by('-started_at'):
            if session.test_id not in active_sessions_map:
                active_sessions_map[session.test_id] = session

        context['tests_with_sessions'] = [
            (t, active_sessions_map.get(t.pk)) for t in tests
        ]
        return context



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

        first_name = data.get('first_name', '')[:150].strip()
        last_name = data.get('last_name', '')[:150].strip()
        if not first_name or not last_name:
            return JsonResponse({'success': False, 'error': 'Имя и фамилия обязательны'}, status=400)

        patient_user = patient.user
        patient_user.first_name = first_name
        patient_user.middle_name = data.get('middle_name', '')[:150].strip()
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
            patient.medical_history = data.get('diagnosis', '')[:5000].strip()
            patient.pain_location = data.get('pain_location', '')[:500].strip()
            duration = data.get('pain_duration', '').strip()
            valid_durations = ['', '1w', '1m', '3m', '6m', '1y', '1y+']
            patient.pain_duration = duration if duration in valid_durations else ''
            patient.save(update_fields=['medical_history', 'pain_location', 'pain_duration'])

        return JsonResponse({
            'success': True,
            'full_name': patient_user.get_full_name(),
            'date_of_birth': profile.date_of_birth.strftime('%d.%m.%Y') if profile.date_of_birth else '',
            'date_of_birth_iso': profile.date_of_birth.strftime('%Y-%m-%d') if profile.date_of_birth else '',
            'diagnosis': patient.medical_history,
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


class PatientExportExcelView(LoginRequiredMixin, View):
    """Выгрузка результатов тестов пациента в Excel.

    GET-параметры date_from / date_to (YYYY-MM-DD) фильтруют период —
    те же параметры, что используются на странице карточки пациента.
    """

    DURATION_LABELS = {
        '1w': 'Менее 1 недели',
        '1m': '1–4 недели',
        '3m': '1–3 месяца',
        '6m': '3–6 месяцев',
        '1y': '6–12 месяцев',
        '1y+': 'Более 1 года',
    }

    def _get_patient(self, user, pk):
        """Возвращает пациента только если у пользователя есть права на просмотр."""
        if user.user_type == 'doctor':
            return get_object_or_404(
                Patient.objects.select_related(
                    'user', 'user__patient_profile', 'assigned_doctor'
                ),
                pk=pk, assigned_doctor=user,
            )
        if user.user_type == 'patient':
            return get_object_or_404(
                Patient.objects.select_related(
                    'user', 'user__patient_profile', 'assigned_doctor'
                ),
                pk=pk, user=user,
            )
        from django.http import Http404
        raise Http404

    def get(self, request, pk):
        import openpyxl
        from datetime import date as date_type
        from openpyxl.styles import Alignment

        patient = self._get_patient(request.user, pk)

        # ── Разбираем фильтр дат ──────────────────────────────────────────
        date_from_str = request.GET.get('date_from', '').strip()
        date_to_str   = request.GET.get('date_to',   '').strip()
        date_from = date_to = None

        if date_from_str:
            try:
                date_from = date_type.fromisoformat(date_from_str)
            except ValueError:
                date_from_str = ''

        if date_to_str:
            try:
                date_to = date_type.fromisoformat(date_to_str)
            except ValueError:
                date_to_str = ''

        # ── Строим queryset результатов ───────────────────────────────────
        results_qs = (
            patient.test_results
            .filter(status='completed')
            .select_related('test')
            .prefetch_related('answers__question__stage')
            .order_by('completed_at')
        )
        if date_from:
            results_qs = results_qs.filter(completed_at__date__gte=date_from)
        if date_to:
            results_qs = results_qs.filter(completed_at__date__lte=date_to)

        results = list(results_qs)

        # ── Загружаем шаблон (read-only — объект не кешируется) ───────────
        template_path = os.path.join(settings.BASE_DIR, 'test-result-template.xlsx')
        if not os.path.exists(template_path):
            raise FileNotFoundError(
                f'Файл шаблона Excel не найден: {template_path}\n'
                'Скопируйте test-result-template.xlsx в корень проекта (рядом с manage.py).'
            )
        wb = openpyxl.load_workbook(template_path)

        # ── Лист 1: Личная информация ─────────────────────────────────────
        ws_info = wb['Личная информация']

        try:
            dob = patient.user.patient_profile.date_of_birth
            dob_str = dob.strftime('%d.%m.%Y') if dob else '—'
        except Exception:
            dob_str = '—'

        doctor = patient.assigned_doctor
        ws_info['B2'] = patient.user.last_name  or '—'
        ws_info['B3'] = patient.user.first_name or '—'
        ws_info['B4'] = getattr(patient.user, 'middle_name', '') or '—'
        ws_info['B5'] = dob_str
        ws_info['B6'] = patient.medical_history or '—'
        ws_info['B7'] = patient.pain_location   or '—'
        ws_info['B8'] = (
            self.DURATION_LABELS.get(patient.pain_duration, '—')
            if patient.pain_duration else '—'
        )
        ws_info['B9'] = doctor.get_full_name() if doctor else '—'

        # ── Лист 2: Результаты тестов ─────────────────────────────────────
        ws_res = wb['Результаты тестов']

        # Переименовываем заголовок колонки C
        ws_res['C2'] = 'Тест ВАШ (VAS), NCS-R, PAINAD'

        # Строка 3 — пустая строка-пример из шаблона; убираем её
        ws_res.delete_rows(3)

        from openpyxl.styles import Border, Side

        center      = Alignment(horizontal='center', vertical='center', wrap_text=True)
        thin_side   = Side(style='thin')
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        # Категории, которые не имеют отдельных шагов DN4/CSI/HADS
        SINGLE_SCORE_CATEGORIES = {'ncsr', 'painad'}

        for result in results:
            # Считаем баллы по шагам сайдбара
            step_scores: dict[int, int] = {}
            for answer in result.answers.all():
                stage = answer.question.stage
                if stage is None:
                    continue
                step = stage.sidebar_step
                step_scores[step] = step_scores.get(step, 0) + answer.score

            pathotype = _get_pathotype_label(
                result.test.category,
                step_scores,
                result.total_score,
                result.conclusion_label,
            )

            is_single_score = result.test.category in SINGLE_SCORE_CATEGORIES
            row = [
                result.completed_at.strftime('%d.%m.%Y %H:%M'),
                pathotype,
                step_scores.get(1) if 1 in step_scores else '—',  # VAS / NCS-R / PAINAD
                '—' if is_single_score else (step_scores.get(2) if 2 in step_scores else '—'),  # DN4
                '—' if is_single_score else (step_scores.get(3) if 3 in step_scores else '—'),  # CSI
                '—' if is_single_score else (step_scores.get(4) if 4 in step_scores else '—'),  # HADS
            ]

            row_idx = ws_res.max_row + 1
            for col_idx, value in enumerate(row, 1):
                cell = ws_res.cell(row=row_idx, column=col_idx, value=value)
                cell.alignment = center
                cell.border    = thin_border

        # ── Границы на заголовочных строках обоих листов ──────────────────
        for ws in (ws_info, ws_res):
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        cell.border = thin_border

        # ── Авторазмер колонок (по длиннейшему значению) ──────────────────
        for ws in (ws_info, ws_res):
            for col_cells in ws.columns:
                max_len = 0
                col_letter = col_cells[0].column_letter
                for cell in col_cells:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max_len + 4

        # ── Формируем имя файла: просто ФИО пациента ─────────────────────
        safe_name = patient.user.get_full_name().replace(' ', '_')
        filename  = f'{safe_name}.xlsx'

        # ── Отдаём файл ───────────────────────────────────────────────────
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        from urllib.parse import quote
        encoded = quote(filename, safe='')
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded}"
        return response
