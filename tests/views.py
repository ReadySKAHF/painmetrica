from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib import messages
from django.utils import timezone

from accounts.mixins import DoctorRequiredMixin, PatientRequiredMixin
from tests.models import Test, TestResult, Answer, Question


# Views для пациентов

class TestListView(PatientRequiredMixin, ListView):
    """Список доступных тестов для пациентов"""

    model = Test
    template_name = 'tests/test_list.html'
    context_object_name = 'tests'

    def get_queryset(self):
        return Test.objects.filter(is_active=True).select_related('created_by')


class TestStartView(PatientRequiredMixin, View):
    """Начать прохождение теста"""

    def post(self, request, pk):
        test = get_object_or_404(Test, pk=pk, is_active=True)
        patient = request.user.patient_record

        # Создаем новый результат
        test_result = TestResult.objects.create(
            test=test,
            patient=patient,
            status='in_progress'
        )

        messages.success(request, f'Вы начали прохождение теста "{test.title}"')
        return redirect('tests:take', pk=test_result.pk)


class TestTakeView(PatientRequiredMixin, DetailView):
    """Прохождение теста"""

    model = TestResult
    template_name = 'tests/test_take.html'
    context_object_name = 'test_result'

    def get_queryset(self):
        return TestResult.objects.filter(
            patient=self.request.user.patient_record,
            status='in_progress'
        ).select_related('test')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object.test.questions.all().prefetch_related('options')
        return context


class TestSubmitView(PatientRequiredMixin, View):
    """Отправка ответов на тест"""

    def post(self, request, pk):
        test_result = get_object_or_404(
            TestResult,
            pk=pk,
            patient=request.user.patient_record,
            status='in_progress'
        )

        total_score = 0
        questions = test_result.test.questions.all()

        for question in questions:
            answer_key = f'question_{question.id}'

            # Создаем или обновляем ответ
            answer, created = Answer.objects.get_or_create(
                result=test_result,
                question=question
            )

            if question.question_type == 'text':
                answer.text_answer = request.POST.get(answer_key, '')

            elif question.question_type == 'single':
                option_id = request.POST.get(answer_key)
                if option_id:
                    answer.selected_options.clear()
                    from tests.models import QuestionOption
                    option = QuestionOption.objects.get(id=option_id)
                    answer.selected_options.add(option)
                    answer.score = option.score
                    total_score += option.score

            elif question.question_type == 'multiple':
                option_ids = request.POST.getlist(answer_key)
                answer.selected_options.clear()
                for option_id in option_ids:
                    from tests.models import QuestionOption
                    option = QuestionOption.objects.get(id=option_id)
                    answer.selected_options.add(option)
                    answer.score += option.score
                total_score += answer.score

            elif question.question_type == 'scale':
                scale_value = request.POST.get(answer_key)
                if scale_value:
                    answer.scale_value = int(scale_value)
                    answer.score = int(scale_value)
                    total_score += int(scale_value)

            answer.save()

        # Обновляем статус и общий балл
        test_result.status = 'completed'
        test_result.total_score = total_score
        test_result.completed_at = timezone.now()
        test_result.save()

        messages.success(request, 'Тест успешно завершен! Ваши результаты сохранены.')
        return redirect('tests:my_results')


class MyResultsView(PatientRequiredMixin, ListView):
    """История результатов тестов пациента"""

    model = TestResult
    template_name = 'tests/my_results.html'
    context_object_name = 'results'
    paginate_by = 10

    def get_queryset(self):
        return TestResult.objects.filter(
            patient=self.request.user.patient_record
        ).select_related('test', 'reviewed_by').order_by('-completed_at')


# Views для докторов

class TestManageListView(DoctorRequiredMixin, ListView):
    """Список тестов для управления (доктора)"""

    model = Test
    template_name = 'tests/test_manage_list.html'
    context_object_name = 'tests'
    paginate_by = 20

    def get_queryset(self):
        return Test.objects.all().select_related('created_by')


class TestCreateView(DoctorRequiredMixin, CreateView):
    """Создание нового теста"""

    model = Test
    template_name = 'tests/test_form.html'
    fields = ['title', 'description', 'instructions', 'is_active']
    success_url = reverse_lazy('tests:manage')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Тест успешно создан.')
        return super().form_valid(form)


class TestUpdateView(DoctorRequiredMixin, UpdateView):
    """Редактирование теста"""

    model = Test
    template_name = 'tests/test_form.html'
    fields = ['title', 'description', 'instructions', 'is_active']
    success_url = reverse_lazy('tests:manage')

    def form_valid(self, form):
        messages.success(self.request, 'Тест обновлен.')
        return super().form_valid(form)


class TestDeleteView(DoctorRequiredMixin, DeleteView):
    """Удаление теста"""

    model = Test
    template_name = 'tests/test_confirm_delete.html'
    success_url = reverse_lazy('tests:manage')
    context_object_name = 'test'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Тест успешно удален.')
        return super().delete(request, *args, **kwargs)


class AllResultsView(DoctorRequiredMixin, ListView):
    """Все результаты тестов для докторов"""

    model = TestResult
    template_name = 'tests/all_results.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        # Показываем результаты только пациентов данного доктора
        return TestResult.objects.filter(
            patient__assigned_doctor=self.request.user,
            status__in=['completed', 'reviewed']
        ).select_related('test', 'patient__user').order_by('-completed_at')
