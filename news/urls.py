from django.urls import path
from news import views

app_name = 'news'

urlpatterns = [
    path('',                         views.NewsListView.as_view(),      name='list'),
    path('add/',                     views.ArticleFormView.as_view(),   name='add'),
    path('<int:pk>/',                views.ArticleDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/',           views.ArticleFormView.as_view(),   name='edit'),
    path('<int:pk>/toggle-publish/', views.ArticlePublishView.as_view(), name='toggle_publish'),
]
