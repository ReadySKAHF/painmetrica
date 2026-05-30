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
        med_ids = cache.get('medications_ids_all')
        if med_ids is None:
            med_ids = list(Medication.objects.values_list('pk', flat=True))
            cache.set('medications_ids_all', med_ids, 1800)
        return Medication.objects.filter(pk__in=med_ids)

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
        ctx['notes_by_medication'] = {str(n.medication_id): n.text for n in notes}
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
        note_key = f'med_note_{self.object.pk}_{self.request.user.pk}'
        doctor_note = cache.get(note_key)
        if doctor_note is None:
            doctor_note = self.object.doctor_notes.filter(doctor=self.request.user).first()
            cache.set(note_key, doctor_note or '', 3600)
        ctx['doctor_note'] = doctor_note if doctor_note else None
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


