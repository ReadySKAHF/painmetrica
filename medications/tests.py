from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import PatientProfile
from medications.models import Medication, MedicationNote, Prescription
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


def make_patient_with_record(email='patient@test.com', doctor=None):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Пётр', last_name='Петров',
        user_type='patient', is_email_verified=True,
    )
    PatientProfile.objects.create(user=user)
    patient = Patient.objects.create(user=user, assigned_doctor=doctor)
    return user, patient


def make_medication(doctor, name='Ибупрофен'):
    return Medication.objects.create(
        name=name,
        medication_type='НПВС',
        prescription_scheme='По 400 мг 3 раза в день',
        side_effects='Тошнота, боль в желудке',
        created_by=doctor,
    )


# ─────────────────────────────────────────────
# Модель Medication
# ─────────────────────────────────────────────

class MedicationModelTests(TestCase):

    def test_создание_лекарства(self):
        doctor = make_doctor()
        med = make_medication(doctor)
        self.assertEqual(med.name, 'Ибупрофен')
        self.assertEqual(med.created_by, doctor)

    def test_строковое_представление(self):
        doctor = make_doctor()
        med = make_medication(doctor, name='Парацетамол')
        self.assertEqual(str(med), 'Парацетамол')


# ─────────────────────────────────────────────
# MedicationListView
# ─────────────────────────────────────────────

class MedicationListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.url = reverse('medications:list')

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_пациент_не_имеет_доступа(self):
        patient_user, _ = make_patient_with_record()
        self.client.force_login(patient_user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_доктор_видит_список_лекарств(self):
        make_medication(self.doctor, 'Ибупрофен')
        make_medication(self.doctor, 'Парацетамол')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_medications'], 2)

    def test_поиск_по_названию(self):
        make_medication(self.doctor, 'Ибупрофен')
        make_medication(self.doctor, 'Парацетамол')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url, {'q': 'Ибу'})
        self.assertEqual(response.status_code, 200)
        meds = list(response.context['medications'])
        self.assertEqual(len(meds), 1)
        self.assertEqual(meds[0].name, 'Ибупрофен')


# ─────────────────────────────────────────────
# MedicationDetailView
# ─────────────────────────────────────────────

class MedicationDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.med = make_medication(self.doctor)
        self.url = reverse('medications:detail', kwargs={'pk': self.med.pk})

    def test_доктор_видит_карточку_лекарства(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['medication'], self.med)

    def test_заметка_отсутствует_по_умолчанию(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertIsNone(response.context['doctor_note'])


# ─────────────────────────────────────────────
# medication_update_notes (AJAX)
# ─────────────────────────────────────────────

class MedicationUpdateNotesTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.med = make_medication(self.doctor)
        self.url = reverse('medications:update_notes', kwargs={'pk': self.med.pk})

    def test_создание_заметки(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {'notes': 'Применять осторожно'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['notes'], 'Применять осторожно')
        self.assertTrue(MedicationNote.objects.filter(medication=self.med, doctor=self.doctor).exists())

    def test_обновление_существующей_заметки(self):
        MedicationNote.objects.create(medication=self.med, doctor=self.doctor, text='Старый текст')
        self.client.force_login(self.doctor)
        self.client.post(self.url, {'notes': 'Новый текст'})
        note = MedicationNote.objects.get(medication=self.med, doctor=self.doctor)
        self.assertEqual(note.text, 'Новый текст')

    def test_пустая_заметка_удаляет_запись(self):
        MedicationNote.objects.create(medication=self.med, doctor=self.doctor, text='Текст')
        self.client.force_login(self.doctor)
        self.client.post(self.url, {'notes': ''})
        self.assertFalse(MedicationNote.objects.filter(medication=self.med, doctor=self.doctor).exists())

    def test_неавторизованный_редиректится(self):
        response = self.client.post(self.url, {'notes': 'Тест'})
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────
# MedicationCreateView / UpdateView
# ─────────────────────────────────────────────

class MedicationCreateViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.url = reverse('medications:create')

    def test_форма_создания_открывается(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_создание_лекарства_через_форму(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {
            'name': 'Новое лекарство',
            'medication_type': 'Антибиотик',
            'prescription_scheme': '1 таблетка 2 раза в день',
            'side_effects': 'Аллергия',
        })
        self.assertRedirects(response, reverse('medications:list'))
        self.assertTrue(Medication.objects.filter(name='Новое лекарство').exists())

    def test_created_by_устанавливается_автоматически(self):
        self.client.force_login(self.doctor)
        self.client.post(self.url, {
            'name': 'Автор тест',
            'medication_type': 'Тип',
            'prescription_scheme': '',
            'side_effects': '',
        })
        med = Medication.objects.get(name='Автор тест')
        self.assertEqual(med.created_by, self.doctor)


# ─────────────────────────────────────────────
# PrescriptionCreateView
# ─────────────────────────────────────────────

class PrescriptionCreateViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient_with_record(doctor=self.doctor)
        self.med = make_medication(self.doctor)
        self.url = reverse('medications:prescription_create')

    def test_форма_назначения_открывается(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_создание_назначения(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {
            'patient': self.patient.pk,
            'medication': self.med.pk,
            'dosage': '400 мг',
            'frequency': '3 раза в день',
            'duration': '7 дней',
            'instructions': '',
            'start_date': '',
            'end_date': '',
        })
        self.assertEqual(Prescription.objects.count(), 1)
        prescription = Prescription.objects.first()
        self.assertEqual(prescription.doctor, self.doctor)
        self.assertEqual(prescription.patient, self.patient)

    def test_форма_показывает_только_своих_пациентов(self):
        other_doctor = make_doctor(email='other@test.com')
        _, other_patient = make_patient_with_record(email='op@test.com', doctor=other_doctor)

        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        patient_queryset = response.context['form'].fields['patient'].queryset
        self.assertNotIn(other_patient, patient_queryset)
        self.assertIn(self.patient, patient_queryset)
