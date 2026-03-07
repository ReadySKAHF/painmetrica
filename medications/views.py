from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from accounts.mixins import DoctorRequiredMixin
from medications.models import Medication, MedicationNote, Prescription


class MedicationListView(DoctorRequiredMixin, ListView):
    """Список лекарств"""

    model = Medication
    template_name = 'medications/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 10

    def get_queryset(self):
        qs = Medication.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '').strip()
        ctx['total_medications'] = Medication.objects.count()
        return ctx


class MedicationDetailView(DoctorRequiredMixin, DetailView):
    """Карточка лекарства"""

    model = Medication
    template_name = 'medications/medication_detail.html'
    context_object_name = 'medication'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['doctor_note'] = self.object.doctor_notes.get(doctor=self.request.user)
        except MedicationNote.DoesNotExist:
            ctx['doctor_note'] = None
        return ctx


class MedicationCreateView(DoctorRequiredMixin, CreateView):
    """Создание нового лекарства"""

    model = Medication
    template_name = 'medications/medication_form.html'
    fields = ['name', 'medication_type', 'prescription_scheme', 'side_effects']
    success_url = reverse_lazy('medications:list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Лекарство успешно добавлено.')
        return super().form_valid(form)


class MedicationUpdateView(DoctorRequiredMixin, UpdateView):
    """Редактирование лекарства"""

    model = Medication
    template_name = 'medications/medication_form.html'
    fields = ['name', 'medication_type', 'prescription_scheme', 'side_effects']
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


@login_required
@require_POST
def medication_update_notes(request, pk):
    """AJAX: сохранить/удалить примечание текущего доктора"""
    medication = get_object_or_404(Medication, pk=pk)
    text = request.POST.get('notes', '').strip()
    if text:
        note, _ = MedicationNote.objects.update_or_create(
            medication=medication,
            doctor=request.user,
            defaults={'text': text}
        )
        return JsonResponse({'status': 'ok', 'notes': note.text})
    else:
        MedicationNote.objects.filter(medication=medication, doctor=request.user).delete()
        return JsonResponse({'status': 'ok', 'notes': ''})


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
        from patients.models import Patient
        form.fields['patient'].queryset = Patient.objects.filter(assigned_doctor=self.request.user)
        return form

    def get_success_url(self):
        return reverse_lazy('patients:detail', kwargs={'pk': self.object.patient.pk})
