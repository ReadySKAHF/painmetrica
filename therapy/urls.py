from django.urls import path
from therapy import views

app_name = 'therapy'

urlpatterns = [
    path('', views.TherapyListView.as_view(), name='list'),
    path('<int:pk>/', views.TherapyDetailView.as_view(), name='detail'),
    path('<int:pk>/update-notes/', views.therapy_update_notes, name='update_notes'),
]
