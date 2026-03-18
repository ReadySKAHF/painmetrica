import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import PatientProfile
from patients.models import Patient

User = get_user_model()


# ─────────────────────────────────────────────
# Вспомогательные фабрики
# ─────────────────────────────────────────────

def make_doctor(email='doctor@test.com', **kwargs):
    return User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Иван', last_name='Иванов',
        user_type='doctor', is_email_verified=True, **kwargs
    )


def make_patient(email='patient@test.com', **kwargs):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Пётр', last_name='Петров',
        user_type='patient', is_email_verified=True, **kwargs
    )
    PatientProfile.objects.create(user=user)
    patient = Patient.objects.create(user=user)
    return user, patient


# ─────────────────────────────────────────────
# Модель Patient
# ─────────────────────────────────────────────

class PatientModelTests(TestCase):

    def test_создание_пациента(self):
        _, patient = make_patient()
        self.assertIsNotNone(patient.pk)
        self.assertIsNone(patient.assigned_doctor)

    def test_назначение_доктора(self):
        doctor = make_doctor()
        _, patient = make_patient()
        patient.assigned_doctor = doctor
        patient.save()
        patient.refresh_from_db()
        self.assertEqual(patient.assigned_doctor, doctor)

    def test_удаление_доктора_обнуляет_поле(self):
        doctor = make_doctor()
        _, patient = make_patient()
        patient.assigned_doctor = doctor
        patient.save()
        doctor.delete()
        patient.refresh_from_db()
        self.assertIsNone(patient.assigned_doctor)


# ─────────────────────────────────────────────
# PatientListView
# ─────────────────────────────────────────────

class PatientListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.url = reverse('patients:list')

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_пациент_не_имеет_доступа(self):
        patient_user, _ = make_patient()
        self.client.force_login(patient_user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_доктор_видит_только_своих_пациентов(self):
        _, patient = make_patient()
        patient.assigned_doctor = self.doctor
        patient.save()

        other_doctor = make_doctor(email='other@test.com')
        _, patient2 = make_patient(email='p2@test.com')
        patient2.assigned_doctor = other_doctor
        patient2.save()

        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['patients'])), 1)

    def test_доктор_не_видит_чужих_пациентов(self):
        other_doctor = make_doctor(email='other@test.com')
        _, patient = make_patient()
        patient.assigned_doctor = other_doctor
        patient.save()

        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(len(list(response.context['patients'])), 0)


# ─────────────────────────────────────────────
# PatientDetailView
# ─────────────────────────────────────────────

class PatientDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.patient_user, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()
        self.url = reverse('patients:detail', kwargs={'pk': self.patient.pk})

    def test_доктор_видит_своего_пациента(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_пациент_видит_свою_карточку(self):
        self.client.force_login(self.patient_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_чужой_доктор_не_видит_пациента(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────
# PatientUpdateAPIView (AJAX)
# ─────────────────────────────────────────────

class PatientUpdateAPIViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.patient_user, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()
        self.url = reverse('patients:update', kwargs={'pk': self.patient.pk})

    def _post_json(self, data):
        return self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def test_доктор_обновляет_данные_пациента(self):
        self.client.force_login(self.doctor)
        response = self._post_json({
            'first_name': 'Новое',
            'last_name': 'Имя',
            'middle_name': '',
            'date_of_birth': '',
            'pain_location': 'Поясница',
            'pain_duration': '1m',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.first_name, 'Новое')

    def test_обновление_без_имени_возвращает_ошибку(self):
        self.client.force_login(self.doctor)
        response = self._post_json({'first_name': '', 'last_name': ''})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_чужой_доктор_не_может_обновить(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self._post_json({'first_name': 'Хак', 'last_name': 'Атака'})
        self.assertEqual(response.status_code, 404)

    def test_неавторизованный_получает_редирект(self):
        response = self._post_json({'first_name': 'А', 'last_name': 'Б'})
        self.assertEqual(response.status_code, 302)
