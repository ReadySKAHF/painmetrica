from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import PatientProfile
from patients.models import Patient
from therapy.models import Therapy, TherapyNote

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


def make_patient_user(email='patient@test.com'):
    user = User.objects.create_user(
        email=email, password='TestPass123!',
        first_name='Пётр', last_name='Петров',
        user_type='patient', is_email_verified=True,
    )
    PatientProfile.objects.create(user=user)
    Patient.objects.create(user=user)
    return user


def make_therapy(doctor, name='ЛФК'):
    return Therapy.objects.create(
        name=name,
        therapy_type='Физиотерапия',
        prescription_scheme='5 занятий в неделю',
        clinical_goal='Восстановление подвижности',
        created_by=doctor,
    )


# ─────────────────────────────────────────────
# Модель Therapy
# ─────────────────────────────────────────────

class TherapyModelTests(TestCase):

    def test_создание_терапии(self):
        doctor = make_doctor()
        therapy = make_therapy(doctor)
        self.assertEqual(therapy.name, 'ЛФК')
        self.assertEqual(therapy.created_by, doctor)

    def test_строковое_представление(self):
        doctor = make_doctor()
        therapy = make_therapy(doctor, name='Массаж')
        self.assertEqual(str(therapy), 'Массаж')

    def test_терапия_без_автора(self):
        therapy = Therapy.objects.create(name='Плавание', created_by=None)
        self.assertIsNone(therapy.created_by)


# ─────────────────────────────────────────────
# Модель TherapyNote
# ─────────────────────────────────────────────

class TherapyNoteModelTests(TestCase):

    def test_создание_примечания(self):
        doctor = make_doctor()
        therapy = make_therapy(doctor)
        note = TherapyNote.objects.create(therapy=therapy, doctor=doctor, text='Осторожно с нагрузками')
        self.assertEqual(note.text, 'Осторожно с нагрузками')
        self.assertEqual(note.therapy, therapy)
        self.assertEqual(note.doctor, doctor)

    def test_уникальность_пары_терапия_доктор(self):
        doctor = make_doctor()
        therapy = make_therapy(doctor)
        TherapyNote.objects.create(therapy=therapy, doctor=doctor, text='Первая')
        with self.assertRaises(Exception):
            TherapyNote.objects.create(therapy=therapy, doctor=doctor, text='Дубль')

    def test_разные_доктора_могут_иметь_примечания_к_одной_терапии(self):
        doctor1 = make_doctor(email='d1@test.com')
        doctor2 = make_doctor(email='d2@test.com')
        therapy = make_therapy(doctor1)
        TherapyNote.objects.create(therapy=therapy, doctor=doctor1, text='Заметка 1')
        TherapyNote.objects.create(therapy=therapy, doctor=doctor2, text='Заметка 2')
        self.assertEqual(TherapyNote.objects.filter(therapy=therapy).count(), 2)


# ─────────────────────────────────────────────
# TherapyListView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class TherapyListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.url = reverse('therapy:list')

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_пациент_не_имеет_доступа(self):
        patient = make_patient_user()
        self.client.force_login(patient)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_доктор_видит_список_терапий(self):
        make_therapy(self.doctor, 'ЛФК')
        make_therapy(self.doctor, 'Массаж')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_therapies'], 2)

    def test_поиск_по_названию(self):
        make_therapy(self.doctor, 'ЛФК')
        make_therapy(self.doctor, 'Массаж')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url, {'q': 'ЛФК'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_therapies'], 1)

    def test_поиск_без_совпадений_возвращает_пустой_список(self):
        make_therapy(self.doctor, 'ЛФК')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url, {'q': 'Несуществующий'})
        self.assertEqual(response.context['total_therapies'], 0)

    def test_контекст_содержит_примечания_текущего_доктора(self):
        therapy = make_therapy(self.doctor, 'ЛФК')
        TherapyNote.objects.create(therapy=therapy, doctor=self.doctor, text='Заметка')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertIn(therapy.pk, response.context['notes_by_therapy'])
        self.assertEqual(response.context['notes_by_therapy'][therapy.pk], 'Заметка')

    def test_примечания_другого_доктора_не_попадают_в_контекст(self):
        therapy = make_therapy(self.doctor, 'ЛФК')
        other_doctor = make_doctor(email='other@test.com')
        TherapyNote.objects.create(therapy=therapy, doctor=other_doctor, text='Чужая заметка')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertNotIn(therapy.pk, response.context['notes_by_therapy'])

    def test_search_query_передаётся_в_контекст(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url, {'q': 'тест'})
        self.assertEqual(response.context['search_query'], 'тест')


# ─────────────────────────────────────────────
# TherapyDetailView
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class TherapyDetailViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.therapy = make_therapy(self.doctor)
        self.url = reverse('therapy:detail', kwargs={'pk': self.therapy.pk})

    def test_доктор_видит_карточку_терапии(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['therapy'], self.therapy)

    def test_примечание_отсутствует_по_умолчанию(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertIsNone(response.context['doctor_note'])

    def test_примечание_отображается_если_есть(self):
        note = TherapyNote.objects.create(therapy=self.therapy, doctor=self.doctor, text='Важно')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.context['doctor_note'], note)

    def test_примечание_другого_доктора_не_отображается(self):
        other_doctor = make_doctor(email='other@test.com')
        TherapyNote.objects.create(therapy=self.therapy, doctor=other_doctor, text='Чужое')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertIsNone(response.context['doctor_note'])

    def test_неавторизованный_редиректится(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_пациент_не_имеет_доступа(self):
        patient = make_patient_user()
        self.client.force_login(patient)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)


# ─────────────────────────────────────────────
# therapy_update_notes (AJAX)
# ─────────────────────────────────────────────

@override_settings(**_NO_REDIS)
class TherapyUpdateNotesTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.therapy = make_therapy(self.doctor)
        self.url = reverse('therapy:update_notes', kwargs={'pk': self.therapy.pk})

    def test_создание_примечания(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {'notes': 'Новое примечание'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['notes'], 'Новое примечание')
        self.assertTrue(TherapyNote.objects.filter(therapy=self.therapy, doctor=self.doctor).exists())

    def test_обновление_существующего_примечания(self):
        TherapyNote.objects.create(therapy=self.therapy, doctor=self.doctor, text='Старый текст')
        self.client.force_login(self.doctor)
        self.client.post(self.url, {'notes': 'Новый текст'})
        note = TherapyNote.objects.get(therapy=self.therapy, doctor=self.doctor)
        self.assertEqual(note.text, 'Новый текст')

    def test_пустое_примечание_удаляет_запись(self):
        TherapyNote.objects.create(therapy=self.therapy, doctor=self.doctor, text='Текст')
        self.client.force_login(self.doctor)
        response = self.client.post(self.url, {'notes': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['notes'], '')
        self.assertFalse(TherapyNote.objects.filter(therapy=self.therapy, doctor=self.doctor).exists())

    def test_примечание_другого_доктора_не_затрагивается(self):
        other_doctor = make_doctor(email='other@test.com')
        TherapyNote.objects.create(therapy=self.therapy, doctor=other_doctor, text='Чужое')
        self.client.force_login(self.doctor)
        self.client.post(self.url, {'notes': 'Своё'})
        self.assertEqual(TherapyNote.objects.filter(therapy=self.therapy).count(), 2)
        self.assertEqual(TherapyNote.objects.get(doctor=other_doctor).text, 'Чужое')

    def test_неавторизованный_редиректится(self):
        response = self.client.post(self.url, {'notes': 'Тест'})
        self.assertEqual(response.status_code, 302)

    def test_get_запрос_не_принимается(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
