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

    # ── Пациент: история результатов (редирект на карточку) ──
    path('my-results/', views.MyResultsView.as_view(), name='my_results'),

    # ── Управление тестами (доктора) ──
    path('manage/', views.TestManageListView.as_view(), name='manage'),
    path('manage/create/', views.TestCreateView.as_view(), name='create'),
    path('manage/<int:pk>/edit/', views.TestUpdateView.as_view(), name='edit'),
    path('manage/<int:pk>/delete/', views.TestDeleteView.as_view(), name='delete'),
    path('results/', views.AllResultsView.as_view(), name='all_results'),
]
