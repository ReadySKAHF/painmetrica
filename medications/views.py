from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages

from accounts.mixins import DoctorRequiredMixin
from medications.models import Medication, Prescription


class MedicationListView(DoctorRequiredMixin, ListView):
    """Список лекарств"""

    model = Medication
    template_name = 'medications/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 20

    def get_queryset(self):
        # Показываем все лекарства
        return Medication.objects.all().select_related('created_by')


class MedicationCreateView(DoctorRequiredMixin, CreateView):
    """Создание нового лекарства"""

    model = Medication
    template_name = 'medications/medication_form.html'
    fields = ['name', 'description', 'dosage_form', 'manufacturer']
    success_url = reverse_lazy('medications:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Лекарство успешно добавлено.')
        return super().form_valid(form)


class MedicationUpdateView(DoctorRequiredMixin, UpdateView):
    """Редактирование лекарства"""

    model = Medication
    template_name = 'medications/medication_form.html'
    fields = ['name', 'description', 'dosage_form', 'manufacturer']
    success_url = reverse_lazy('medications:list')

    def form_valid(self, form):
        messages.success(self.request, 'Лекарство обновлено.')
        return super().form_valid(form)


class MedicationDeleteView(DoctorRequiredMixin, DeleteView):
    """Удаление лекарства"""

    model = Medication
    template_name = 'medications/medication_confirm_delete.html'
    success_url = reverse_lazy('medications:list')
    context_object_name = 'medication'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Лекарство успешно удалено.')
        return super().delete(request, *args, **kwargs)


class PrescriptionCreateView(DoctorRequiredMixin, CreateView):
    """Назначение лекарства пациенту"""

    model = Prescription
    template_name = 'medications/prescription_form.html'
    fields = ['patient', 'medication', 'dosage', 'frequency', 'duration', 'instructions', 'start_date', 'end_date']

    def form_valid(self, form):
        form.instance.doctor = self.request.user
        messages.success(self.request, 'Лекарство успешно назначено пациенту.')
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Ограничиваем выбор только своими пациентами
        from patients.models import Patient
        form.fields['patient'].queryset = Patient.objects.filter(assigned_doctor=self.request.user)
        return form

    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.patient.pk})
