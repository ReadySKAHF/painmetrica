from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator


class HomeView(TemplateView):
    """Главная страница для неавторизованных пользователей"""

    template_name = 'core/home.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        return super().get(request, *args, **kwargs)


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

            patients_qs = Patient.objects.filter(
                assigned_doctor=user
            ).select_related('user', 'user__patient_profile')

            if search_query:
                patients_qs = patients_qs.filter(
                    Q(user__first_name__icontains=search_query) |
                    Q(user__last_name__icontains=search_query) |
                    Q(user__middle_name__icontains=search_query)
                )
            elif adv_last_name or adv_first_name or adv_middle_name:
                adv_filter = Q()
                if adv_last_name:
                    adv_filter &= Q(user__last_name__icontains=adv_last_name)
                if adv_first_name:
                    adv_filter &= Q(user__first_name__icontains=adv_first_name)
                if adv_middle_name:
                    adv_filter &= Q(user__middle_name__icontains=adv_middle_name)
                patients_qs = patients_qs.filter(adv_filter)

            total_patients = Patient.objects.filter(assigned_doctor=user).count()
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

        elif user.user_type == 'patient':
            context['is_patient'] = True
            try:
                patient = user.patient_record
                context['assigned_doctor'] = patient.assigned_doctor
                context['patient_pk'] = patient.pk
            except Exception:
                context['assigned_doctor'] = None
                context['patient_pk'] = None

        return render(request, self.template_name, context)
