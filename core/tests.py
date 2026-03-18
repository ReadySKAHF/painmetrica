from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import PatientProfile
from patients.models import Patient

User = get_user_model()


def make_doctor(email='doctor@test.com'):
    return User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Иван', last_name='Иванов',
        user_type='doctor', is_email_verified=True,
    )


def make_patient(email='patient@test.com', doctor=None):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Пётр', last_name='Петров',
        user_type='patient', is_email_verified=True,
    )
    PatientProfile.objects.create(user=user)
    Patient.objects.create(user=user, assigned_doctor=doctor)
    return user


# ─────────────────────────────────────────────
# HomeView
# ─────────────────────────────────────────────

class HomeViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('core:home')

    def test_главная_открывается_для_анонима(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_авторизованный_редиректится_на_дашборд(self):
        doctor = make_doctor()
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('core:dashboard'))


# ─────────────────────────────────────────────
# DashboardView
# ─────────────────────────────────────────────

class DashboardViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('core:dashboard')

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_доктор_видит_дашборд(self):
        doctor = make_doctor()
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_doctor'])

    def test_пациент_видит_дашборд(self):
        patient_user = make_patient()
        self.client.force_login(patient_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_patient'])

    def test_дашборд_доктора_содержит_список_пациентов(self):
        doctor = make_doctor()
        make_patient(email='p1@test.com', doctor=doctor)
        make_patient(email='p2@test.com', doctor=doctor)
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_patients'], 2)

    def test_дашборд_доктора_не_содержит_чужих_пациентов(self):
        doctor = make_doctor()
        other_doctor = make_doctor(email='other@test.com')
        make_patient(email='p1@test.com', doctor=other_doctor)
        self.client.force_login(doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_patients'], 0)

    def test_поиск_пациентов_на_дашборде(self):
        doctor = make_doctor()
        make_patient(email='p1@test.com', doctor=doctor)
        self.client.force_login(doctor)
        response = self.client.get(self.url, {'q': 'Петров'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['patients'])), 1)

    def test_поиск_без_совпадений(self):
        doctor = make_doctor()
        make_patient(email='p1@test.com', doctor=doctor)
        self.client.force_login(doctor)
        response = self.client.get(self.url, {'q': 'Несуществующий'})
        self.assertEqual(len(list(response.context['patients'])), 0)

    def test_пациент_видит_своего_врача(self):
        doctor = make_doctor()
        patient_user = make_patient(doctor=doctor)
        self.client.force_login(patient_user)
        response = self.client.get(self.url)
        self.assertEqual(response.context['assigned_doctor'], doctor)
