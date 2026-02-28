from django.urls import path
from tests import views

app_name = 'tests'

urlpatterns = [
    # Для пациентов
    path('', views.TestListView.as_view(), name='list'),
    path('<int:pk>/start/', views.TestStartView.as_view(), name='start'),
    path('result/<int:pk>/', views.TestTakeView.as_view(), name='take'),
    path('result/<int:pk>/submit/', views.TestSubmitView.as_view(), name='submit'),
    path('my-results/', views.MyResultsView.as_view(), name='my_results'),

    # Для докторов
    path('manage/', views.TestManageListView.as_view(), name='manage'),
    path('manage/create/', views.TestCreateView.as_view(), name='create'),
    path('manage/<int:pk>/edit/', views.TestUpdateView.as_view(), name='edit'),
    path('manage/<int:pk>/delete/', views.TestDeleteView.as_view(), name='delete'),
    path('results/', views.AllResultsView.as_view(), name='all_results'),
]
