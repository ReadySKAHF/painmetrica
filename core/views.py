from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator


def handler429(request, exception=None):
    return render(request, '429.html', status=429)


class HomeView(TemplateView):
    """Главная страница для неавторизованных пользователей"""

    template_name = 'core/home.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        from news.models import Article
        articles_qs = Article.objects.filter(status=Article.STATUS_PUBLISHED)
        paginator = Paginator(articles_qs, 10)
        page_obj = paginator.get_page(request.GET.get('page', 1))
        return render(request, self.template_name, {'articles': page_obj, 'page_obj': page_obj})


class DocumentsView(LoginRequiredMixin, View):
    template_name = 'core/documents.html'

    def get(self, request, *args, **kwargs):
        doc_type = request.GET.get('doc', 'agreement')
        if doc_type not in ('agreement', 'policy'):
            doc_type = 'agreement'
        return render(request, self.template_name, {'doc_type': doc_type})


class DashboardView(LoginRequiredMixin, View):
    """Dashboard после входа — единая страница для докторов и пациентов"""

    template_name = 'core/dashboard.html'

    def get(self, request, *args, **kwargs):
        user = request.user
        context = {}

        if user.user_type == 'doctor':
            from patients.models import Patient
            from django.db.models import Q
            search_query = request.GET.get('q', '').strip()
            adv_last_name = request.GET.get('last_name', '').strip()
            adv_first_name = request.GET.get('first_name', '').strip()
            adv_middle_name = request.GET.get('middle_name', '').strip()
            adv_dob = request.GET.get('dob', '').strip()
            adv_diagnosis = request.GET.get('diagnosis', '').strip()

            patients_qs = Patient.objects.filter(
                assigned_doctor=user
            ).select_related('user', 'user__patient_profile')

            if search_query:
                patients_qs = patients_qs.filter(
                    Q(user__first_name__icontains=search_query) |
                    Q(user__last_name__icontains=search_query) |
                    Q(user__middle_name__icontains=search_query)
                )
            elif adv_last_name or adv_first_name or adv_middle_name or adv_dob or adv_diagnosis:
                adv_filter = Q()
                if adv_last_name:
                    adv_filter &= Q(user__last_name__icontains=adv_last_name)
                if adv_first_name:
                    adv_filter &= Q(user__first_name__icontains=adv_first_name)
                if adv_middle_name:
                    adv_filter &= Q(user__middle_name__icontains=adv_middle_name)
                if adv_dob:
                    from datetime import datetime
                    try:
                        dob_parsed = datetime.strptime(adv_dob, '%d.%m.%Y').date()
                        adv_filter &= Q(user__patient_profile__date_of_birth=dob_parsed)
                    except ValueError:
                        pass
                if adv_diagnosis:
                    adv_filter &= Q(medical_history__icontains=adv_diagnosis)
                patients_qs = patients_qs.filter(adv_filter)

            total_patients = patients_qs.count()
            paginator = Paginator(patients_qs, 10)
            page = request.GET.get('page', 1)
            patients_page = paginator.get_page(page)

            context['is_doctor'] = True
            context['patients'] = patients_page
            context['total_patients'] = total_patients
            context['search_query'] = search_query
            context['adv_last_name'] = adv_last_name
            context['adv_first_name'] = adv_first_name
            context['adv_middle_name'] = adv_middle_name
            context['adv_dob'] = adv_dob
            context['adv_diagnosis'] = adv_diagnosis

        elif user.user_type == 'patient':
            try:
                patient = user.patient_record
                profile = user.patient_profile
                if not profile.has_seen_welcome:
                    return redirect('patients:welcome')
                return redirect('patients:detail', pk=patient.pk)
            except Exception:
                return redirect('patients:welcome')

        from datetime import date
        context['today_iso'] = date.today().isoformat()
        return render(request, self.template_name, context)
