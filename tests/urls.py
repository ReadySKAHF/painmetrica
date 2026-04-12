from django.urls import path
from tests import views

app_name = 'tests'

urlpatterns = [
    # ── Прохождение теста ──
    # Пациент запускает тест за себя
    path('<int:pk>/start/', views.PatientStartTestView.as_view(), name='start'),
    # Доктор запускает тест за пациента
    path('<int:pk>/start/patient/<int:patient_id>/', views.DoctorStartTestView.as_view(), name='start_for_patient'),
    # Этап теста (UUID в URL)
    path('session/<uuid:session_id>/stage/<int:order>/', views.StageView.as_view(), name='stage'),
    # AJAX: сохранение прогресса
    path('session/<uuid:session_id>/save/', views.SaveProgressView.as_view(), name='save_progress'),
    # Страница результатов
    path('session/<uuid:session_id>/result/', views.ResultView.as_view(), name='result'),
    # Детальные ответы по шагу
    path('session/<uuid:session_id>/result/<int:sidebar_step>/', views.ResultDetailView.as_view(), name='result_detail'),

    # ── API: прямая отправка баллов ──
    path('api/submit-scores/', views.ScoreSubmitAPIView.as_view(), name='api_submit_scores'),

    # ── Сравнение результатов тестов пациента ──
    path('patient/<int:patient_pk>/compare/', views.TestCompareView.as_view(), name='compare'),

    # ── Методика расчёта тестов ──
    path('methodology/', views.TestMethodologyView.as_view(), name='methodology'),
]
