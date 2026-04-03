from django.urls import path
from medications import views

app_name = 'medications'

urlpatterns = [
    path('', views.MedicationListView.as_view(), name='list'),
    path('<int:pk>/', views.MedicationDetailView.as_view(), name='detail'),
    path('<int:pk>/update-notes/', views.medication_update_notes, name='update_notes'),
]
