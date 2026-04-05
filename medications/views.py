from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from accounts.mixins import DoctorRequiredMixin
from medications.models import Medication, MedicationNote


class MedicationListView(DoctorRequiredMixin, ListView):
    """Список лекарств"""

    model = Medication
    template_name = 'medications/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 10

    def get_queryset(self):
        q = self.request.GET.get('q', '').strip()
        if q:
            return Medication.objects.filter(name__icontains=q)
        cached = cache.get('medications_all')
        if cached is None:
            cached = list(Medication.objects.all())
            cache.set('medications_all', cached, 1800)
        return cached

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '').strip()
        ol = self.object_list
        ctx['total_medications'] = len(ol) if isinstance(ol, list) else ol.count()

        # Примечания текущего доктора, индексированные по medication_id
        medication_ids = [m.pk for m in ctx['medications']]
        notes = MedicationNote.objects.filter(
            doctor=self.request.user,
            medication_id__in=medication_ids
        )
        ctx['notes_by_medication'] = {n.medication_id: n.text for n in notes}
        return ctx


class MedicationDetailView(DoctorRequiredMixin, DetailView):
    """Карточка лекарства"""

    model = Medication
    template_name = 'medications/medication_detail.html'
    context_object_name = 'medication'

    def get_object(self, queryset=None):
        pk = self.kwargs['pk']
        key = f'medication:{pk}'
        obj = cache.get(key)
        if obj is None:
            obj = super().get_object(queryset)
            cache.set(key, obj, 1800)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['doctor_note'] = self.object.doctor_notes.get(doctor=self.request.user)
        except MedicationNote.DoesNotExist:
            ctx['doctor_note'] = None
        return ctx



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


