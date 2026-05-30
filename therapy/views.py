from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from accounts.mixins import DoctorRequiredMixin
from therapy.models import Therapy, TherapyNote


class TherapyListView(DoctorRequiredMixin, ListView):
    """Список терапий"""

    model = Therapy
    template_name = 'therapy/therapy_list.html'
    context_object_name = 'therapies'
    paginate_by = 10

    def get_queryset(self):
        q = self.request.GET.get('q', '').strip()
        if q:
            return Therapy.objects.filter(name__icontains=q)
        therapy_ids = cache.get('therapies_ids_all')
        if therapy_ids is None:
            therapy_ids = list(Therapy.objects.values_list('pk', flat=True))
            cache.set('therapies_ids_all', therapy_ids, 1800)
        return Therapy.objects.filter(pk__in=therapy_ids)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.request.GET.get('q', '').strip()
        ol = self.object_list
        ctx['total_therapies'] = len(ol) if isinstance(ol, list) else ol.count()

        # Примечания текущего доктора, индексированные по therapy_id
        therapy_ids = [t.pk for t in ctx['therapies']]
        notes = TherapyNote.objects.filter(
            doctor=self.request.user,
            therapy_id__in=therapy_ids
        )
        ctx['notes_by_therapy'] = {n.therapy_id: n.text for n in notes}
        return ctx


class TherapyDetailView(DoctorRequiredMixin, DetailView):
    """Карточка терапии"""

    model = Therapy
    template_name = 'therapy/therapy_detail.html'
    context_object_name = 'therapy'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx['doctor_note'] = self.object.doctor_notes.get(doctor=self.request.user)
        except TherapyNote.DoesNotExist:
            ctx['doctor_note'] = None
        return ctx


@login_required
@require_POST
def therapy_update_notes(request, pk):
    """AJAX: сохранить/удалить примечание текущего доктора"""
    therapy = get_object_or_404(Therapy, pk=pk)
    text = request.POST.get('notes', '').strip()
    if text:
        note, _ = TherapyNote.objects.update_or_create(
            therapy=therapy,
            doctor=request.user,
            defaults={'text': text}
        )
        return JsonResponse({'status': 'ok', 'notes': note.text})
    else:
        TherapyNote.objects.filter(therapy=therapy, doctor=request.user).delete()
        return JsonResponse({'status': 'ok', 'notes': ''})
