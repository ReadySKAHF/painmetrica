from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PatientProfile
from patients.models import Patient
from tests.models import (
    Answer, Question, QuestionOption, ScoreRange,
    Stage, Test, TestResult, TestSession,
)

User = get_user_model()


# ─────────────────────────────────────────────
# Вспомогательные фабрики
# ─────────────────────────────────────────────

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
    patient = Patient.objects.create(user=user, assigned_doctor=doctor)
    return user, patient


def make_simple_test(doctor, title='Тест ВАШ'):
    """Создаёт тест с одним этапом и одним шкальным вопросом."""
    test = Test.objects.create(title=title, description='Описание', created_by=doctor, is_active=True)
    stage = Stage.objects.create(
        test=test, name='ВАШ', description='Шкала боли',
        page_title='Оцените боль', order=1, sidebar_step=1,
    )
    Question.objects.create(
        stage=stage, question_text='Интенсивность боли',
        question_type='scale', order=1,
        scale_min=0, scale_max=10, is_required=True,
    )
    ScoreRange.objects.create(
        test=test, sidebar_step=1,
        min_score=0, max_score=3,
        label='Лёгкая боль', conclusion='Боль незначительна.',
    )
    ScoreRange.objects.create(
        test=test, sidebar_step=1,
        min_score=4, max_score=10,
        label='Умеренная боль', conclusion='Требуется лечение.',
    )
    return test


def make_single_choice_test(doctor):
    """Создаёт тест с одним этапом и одним вопросом с одиночным выбором."""
    test = Test.objects.create(title='Тест одиночный', description='', created_by=doctor, is_active=True)
    stage = Stage.objects.create(
        test=test, name='Шаг 1', description='',
        page_title='Вопрос 1', order=1, sidebar_step=1,
    )
    question = Question.objects.create(
        stage=stage, question_text='Вопрос?',
        question_type='single', order=1, is_required=True,
    )
    QuestionOption.objects.create(question=question, option_text='Нет', order=1, score=0)
    QuestionOption.objects.create(question=question, option_text='Да', order=2, score=1)
    ScoreRange.objects.create(test=test, min_score=0, max_score=0, label='Норма', conclusion='Всё хорошо.')
    ScoreRange.objects.create(test=test, min_score=1, max_score=1, label='Патология', conclusion='Требуется осмотр.')
    return test


# ─────────────────────────────────────────────
# Модели тестовой системы
# ─────────────────────────────────────────────

class TestModelTests(TestCase):

    def test_создание_теста(self):
        doctor = make_doctor()
        test = Test.objects.create(title='DN4', description='Нейропатическая боль', created_by=doctor)
        self.assertEqual(str(test), 'DN4')
        self.assertTrue(test.is_active)

    def test_создание_этапа(self):
        doctor = make_doctor()
        test = make_simple_test(doctor)
        self.assertEqual(test.stages.count(), 1)

    def test_создание_вопроса_с_вариантами(self):
        doctor = make_doctor()
        test = make_single_choice_test(doctor)
        stage = test.stages.first()
        question = stage.questions.first()
        self.assertEqual(question.options.count(), 2)
        self.assertEqual(question.question_type, 'single')


class ScoreRangeTests(TestCase):

    def test_диапазон_подбирается_по_баллу(self):
        doctor = make_doctor()
        test = make_simple_test(doctor)
        match = ScoreRange.objects.filter(
            test=test, sidebar_step=1,
            min_score__lte=2, max_score__gte=2
        ).first()
        self.assertIsNotNone(match)
        self.assertEqual(match.label, 'Лёгкая боль')

    def test_диапазон_для_высокого_балла(self):
        doctor = make_doctor()
        test = make_simple_test(doctor)
        match = ScoreRange.objects.filter(
            test=test, sidebar_step=1,
            min_score__lte=7, max_score__gte=7
        ).first()
        self.assertEqual(match.label, 'Умеренная боль')


# ─────────────────────────────────────────────
# TestSession
# ─────────────────────────────────────────────

class TestSessionTests(TestCase):

    def setUp(self):
        self.doctor = make_doctor()
        _, self.patient = make_patient(doctor=self.doctor)
        self.test = make_simple_test(self.doctor)

    def test_создание_сессии(self):
        session = TestSession.objects.create(
            test=self.test,
            patient=self.patient,
            taken_by=self.doctor,
        )
        self.assertEqual(session.status, 'in_progress')
        self.assertIsNotNone(session.pk)

    def test_pk_является_uuid(self):
        import uuid
        session = TestSession.objects.create(
            test=self.test, patient=self.patient, taken_by=self.doctor,
        )
        self.assertIsInstance(session.pk, uuid.UUID)

    def test_answers_data_по_умолчанию_пустой_словарь(self):
        session = TestSession.objects.create(
            test=self.test, patient=self.patient, taken_by=self.doctor,
        )
        self.assertEqual(session.answers_data, {})


# ─────────────────────────────────────────────
# Представление: запуск теста доктором
# ─────────────────────────────────────────────

class DoctorStartTestViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient(doctor=self.doctor)
        self.test = make_simple_test(self.doctor)
        self.url = reverse('tests:start_for_patient', kwargs={
            'pk': self.test.pk,
            'patient_id': self.patient.pk,
        })

    def test_доктор_создаёт_сессию(self):
        self.client.force_login(self.doctor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TestSession.objects.count(), 1)
        session = TestSession.objects.first()
        self.assertEqual(session.taken_by, self.doctor)
        self.assertEqual(session.patient, self.patient)

    def test_чужой_доктор_не_может_запустить_тест(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(TestSession.objects.count(), 0)

    def test_неавторизованный_редиректится(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TestSession.objects.count(), 0)


# ─────────────────────────────────────────────
# Представление: прохождение этапа (StageView)
# ─────────────────────────────────────────────

class StageViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        _, self.patient = make_patient(doctor=self.doctor)
        self.test = make_simple_test(self.doctor)
        self.session = TestSession.objects.create(
            test=self.test, patient=self.patient, taken_by=self.doctor,
        )
        self.stage = self.test.stages.first()
        self.url = reverse('tests:stage', kwargs={
            'session_id': self.session.pk,
            'order': self.stage.order,
        })

    def test_доктор_открывает_этап(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stage'], self.stage)

    def test_чужой_пользователь_получает_403(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_post_на_последнем_этапе_завершает_сессию(self):
        question = self.stage.questions.first()
        self.client.force_login(self.doctor)
        self.client.post(self.url, {f'q_{question.pk}': '5'})
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'completed')

    def test_завершение_создаёт_test_result(self):
        question = self.stage.questions.first()
        self.client.force_login(self.doctor)
        self.client.post(self.url, {f'q_{question.pk}': '3'})
        self.assertTrue(TestResult.objects.filter(session=self.session).exists())

    def test_итоговый_балл_соответствует_ответу(self):
        question = self.stage.questions.first()
        self.client.force_login(self.doctor)
        self.client.post(self.url, {f'q_{question.pk}': '7'})
        result = TestResult.objects.get(session=self.session)
        self.assertEqual(result.total_score, 7)

    def test_заключение_подбирается_по_баллу(self):
        question = self.stage.questions.first()
        self.client.force_login(self.doctor)
        self.client.post(self.url, {f'q_{question.pk}': '2'})
        result = TestResult.objects.get(session=self.session)
        self.assertEqual(result.conclusion_label, 'Лёгкая боль')


# ─────────────────────────────────────────────
# Представление: результаты (ResultView)
# ─────────────────────────────────────────────

class ResultViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.patient_user, self.patient = make_patient(doctor=self.doctor)
        self.test = make_simple_test(self.doctor)

        self.session = TestSession.objects.create(
            test=self.test, patient=self.patient,
            taken_by=self.doctor, status='completed',
            completed_at=timezone.now(),
        )
        self.result = TestResult.objects.create(
            session=self.session, test=self.test,
            patient=self.patient, taken_by=self.doctor,
            total_score=5, conclusion_label='Умеренная боль',
            status='completed',
        )
        self.url = reverse('tests:result', kwargs={'session_id': self.session.pk})

    def test_доктор_видит_результат(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result'], self.result)

    def test_пациент_видит_свой_результат(self):
        self.client.force_login(self.patient_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_чужой_доктор_получает_403(self):
        other_doctor = make_doctor(email='other@test.com')
        self.client.force_login(other_doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


# ─────────────────────────────────────────────
# Управление тестами (TestManageListView)
# ─────────────────────────────────────────────

class TestManageListViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.doctor = make_doctor()
        self.url = reverse('tests:manage')

    def test_доктор_видит_список_тестов(self):
        make_simple_test(self.doctor, 'Тест 1')
        make_simple_test(self.doctor, 'Тест 2')
        self.client.force_login(self.doctor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['tests'].count(), 2)

    def test_пациент_не_имеет_доступа(self):
        _, patient = make_patient(doctor=self.doctor)
        patient_user = patient.user
        self.client.force_login(patient_user)
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)
