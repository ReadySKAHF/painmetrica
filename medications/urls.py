from django.urls import path
from medications import views

app_name = 'medications'

urlpatterns = [
    path('', views.MedicationListView.as_view(), name='list'),
    path('<int:pk>/', views.MedicationDetailView.as_view(), name='detail'),
    path('<int:pk>/update-notes/', views.medication_update_notes, name='update_notes'),
    path('create/', views.MedicationCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', views.MedicationUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.MedicationDeleteView.as_view(), name='delete'),
    path('prescriptions/create/', views.PrescriptionCreateView.as_view(), name='prescription_create'),
]
