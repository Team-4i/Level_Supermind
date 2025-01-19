from django.urls import path
from . import views

app_name = 'webscraper'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('new/', views.new_task, name='new_task'),
    path('<int:task_id>/', views.task_detail, name='task_detail'),
] 