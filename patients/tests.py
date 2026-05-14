import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import PatientProfile
from patients.models import Patient

User = get_user_model()

_NO_REDIS = dict(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    SESSION_ENGINE='django.contrib.sessions.backends.db',
)


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
# PatientDetailView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
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

@override_settings(**_NO_REDIS)
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


# ─────────────────────────────────────────────
# Поля архивации Patient
# ─────────────────────────────────────────────

class PatientArchivalFieldsTests(TestCase):

    def test_пациент_не_архивирован_по_умолчанию(self):
        _, patient = make_patient()
        self.assertFalse(patient.is_archived)
        self.assertIsNone(patient.archived_at)
        self.assertIsNone(patient.scheduled_deletion_at)

    def test_архивация_пациента(self):
        from django.utils import timezone
        _, patient = make_patient()
        now = timezone.now()
        patient.is_archived = True
        patient.archived_at = now
        patient.save()
        patient.refresh_from_db()
        self.assertTrue(patient.is_archived)
        self.assertIsNotNone(patient.archived_at)


# ─────────────────────────────────────────────
# Модель Conclusion
# ─────────────────────────────────────────────

class ConclusionModelTests(TestCase):

    def setUp(self):
        from patients.models import Conclusion
        self.Conclusion = Conclusion
        self.doctor = make_doctor()
        _, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()

    def test_создание_заключения(self):
        conclusion = self.Conclusion.objects.create(
            patient=self.patient,
            doctor=self.doctor,
        )
        self.assertIsNotNone(conclusion.pk)
        self.assertEqual(conclusion.patient, self.patient)
        self.assertEqual(conclusion.doctor, self.doctor)
        self.assertIsNone(conclusion.last_test_result)

    def test_строковое_представление_заключения(self):
        conclusion = self.Conclusion.objects.create(
            patient=self.patient,
            doctor=self.doctor,
        )
        self.assertIn('Пациент', str(conclusion))

    def test_несколько_заключений_для_пациента(self):
        self.Conclusion.objects.create(patient=self.patient, doctor=self.doctor)
        self.Conclusion.objects.create(patient=self.patient, doctor=self.doctor)
        self.assertEqual(self.Conclusion.objects.filter(patient=self.patient).count(), 2)


# ─────────────────────────────────────────────
# ConclusionListView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ConclusionListViewTests(TestCase):

    def setUp(self):
        from patients.models import Conclusion
        self.Conclusion = Conclusion
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()
        self.url = reverse('patients:conclusion_history', kwargs={'pk': self.patient.pk})

    def test_доктор_видит_историю_заключений(self):
        self.Conclusion.objects.create(patient=self.patient, doctor=self.doctor)
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_чужой_доктор_получает_404(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_список_заключений_пуст_по_умолчанию(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)

    def test_список_содержит_созданные_заключения(self):
        self.Conclusion.objects.create(patient=self.patient, doctor=self.doctor)
        self.Conclusion.objects.create(patient=self.patient, doctor=self.doctor)
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_count'], 2)


# ─────────────────────────────────────────────
# ConclusionMedicineView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ConclusionMedicineViewTests(TestCase):

    def setUp(self):
        from medications.models import Medication
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()
        self.med = Medication.objects.create(
            name='Ибупрофен',
            medication_type='НПВС',
            prescription_scheme='По 400 мг',
            created_by=self.doctor,
        )
        self.url = reverse('patients:conclusion_medicine', kwargs={'pk': self.patient.pk})

    def test_доктор_видит_страницу_выбора_лекарств(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_чужой_доктор_получает_404(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_post_сохраняет_выбранные_лекарства_в_сессию(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {
            'medication_ids': [str(self.med.pk)],
            f'scheme_{self.med.pk}': 'По 400 мг 3 раза',
        })
        self.assertEqual(response.status_code, 302)
        session = self.client.session
        self.assertIn(f'conclusion_med_ids_{self.patient.pk}', session)
        self.assertIn(self.med.pk, session[f'conclusion_med_ids_{self.patient.pk}'])

    def test_post_редиректит_на_реабилитацию(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {'medication_ids': []})
        self.assertRedirects(
            response,
            reverse('patients:conclusion_rehabilitation', kwargs={'pk': self.patient.pk}),
        )


# ─────────────────────────────────────────────
# ConclusionRehabilitationView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class ConclusionRehabilitationViewTests(TestCase):

    def setUp(self):
        from medications.models import Medication
        from therapy.models import Therapy
        from patients.models import Conclusion, ConclusionMedication, ConclusionTherapy
        self.Conclusion = Conclusion
        self.ConclusionMedication = ConclusionMedication
        self.ConclusionTherapy = ConclusionTherapy
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient()
        self.patient.assigned_doctor = self.doctor
        self.patient.save()
        self.med = Medication.objects.create(
            name='Ибупрофен', medication_type='НПВС',
            prescription_scheme='По 400 мг', created_by=self.doctor,
        )
        self.therapy = Therapy.objects.create(
            name='ЛФК', therapy_type='Физиотерапия',
            created_by=self.doctor,
        )
        self.url = reverse('patients:conclusion_rehabilitation', kwargs={'pk': self.patient.pk})

    def test_доктор_видит_страницу_выбора_терапий(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_чужой_доктор_получает_404(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def _set_session_med_data(self):
        session = self.client.session
        session[f'conclusion_med_ids_{self.patient.pk}'] = [self.med.pk]
        session[f'conclusion_med_schemes_{self.patient.pk}'] = {str(self.med.pk): 'По 400 мг 3 раза'}
        session.save()

    def test_post_создаёт_заключение(self):
        self.client.force_login(self.doctor)
        self._set_session_med_data()
        self.client.post(self.url, {'therapy_ids': []})
        self.assertEqual(self.Conclusion.objects.filter(patient=self.patient).count(), 1)

    def test_post_добавляет_лекарства_в_заключение(self):
        self.client.force_login(self.doctor)
        self._set_session_med_data()
        self.client.post(self.url, {'therapy_ids': []})
        conclusion = self.Conclusion.objects.get(patient=self.patient)
        self.assertEqual(self.ConclusionMedication.objects.filter(conclusion=conclusion).count(), 1)
        self.assertEqual(
            self.ConclusionMedication.objects.get(conclusion=conclusion).medication,
            self.med,
        )

    def test_post_добавляет_терапии_в_заключение(self):
        self.client.force_login(self.doctor)
        self._set_session_med_data()
        self.client.post(self.url, {
            'therapy_ids': [str(self.therapy.pk)],
            f'scheme_{self.therapy.pk}': '5 занятий в неделю',
        })
        conclusion = self.Conclusion.objects.get(patient=self.patient)
        self.assertEqual(self.ConclusionTherapy.objects.filter(conclusion=conclusion).count(), 1)

    def test_post_очищает_данные_сессии(self):
        self.client.force_login(self.doctor)
        self._set_session_med_data()
        self.client.post(self.url, {'therapy_ids': []})
        session = self.client.session
        self.assertNotIn(f'conclusion_med_ids_{self.patient.pk}', session)
        self.assertNotIn(f'conclusion_med_schemes_{self.patient.pk}', session)

    def test_post_редиректит_на_карточку_пациента(self):
        self.client.force_login(self.doctor)
        self._set_session_med_data()
        response = self.client.post(self.url, {'therapy_ids': []})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('patients:detail', kwargs={'pk': self.patient.pk}), response['Location'])
