from django.urls import path
from patients import views

app_name = 'patients'

urlpatterns = [
    path('my-profile/', views.PatientMyProfileView.as_view(), name='my_profile'),
    path('<int:pk>/', views.PatientDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.PatientUpdateAPIView.as_view(), name='update'),
    path('<int:pk>/export-excel/', views.PatientExportExcelView.as_view(), name='export_excel'),
]
