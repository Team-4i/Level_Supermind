from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('art/', views.art_list, name='art_list'),
    path('art/create/', views.art_create, name='art_create'),
    path('art/<int:pk>/', views.art_detail, name='art_detail'),
    path('art/<int:pk>/edit/', views.art_edit, name='art_edit'),
    path('art/<int:pk>/generate/', views.art_generate, name='art_generate'),
    path('art/<int:pk>/analytics/', views.art_analytics, name='art_analytics'),
] 