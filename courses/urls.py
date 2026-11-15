from django.urls import path

from . import views, views_account, views_course, views_manage

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('me/', views_account.profile, name='profile'),
    path('me/settings/', views_account.settings_view, name='settings'),
    path('manage/users/import/', views_manage.import_users, name='import_users'),
    path('manage/users/import/template.xlsx', views_manage.import_template, name='import_template'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('courses/<int:course_pk>/assignments/new/', views.assignment_create, name='assignment_create'),
    path('courses/<int:pk>/members/', views_course.course_members, name='course_members'),
    path('courses/<int:pk>/members/<int:user_id>/', views_course.member_progress, name='member_progress'),
    path('courses/<int:pk>/grades/', views_course.gradebook, name='gradebook'),
    path('assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:pk>/edit/', views.assignment_edit, name='assignment_edit'),
    path('assignments/<int:pk>/export.csv', views.export_csv, name='export_csv'),
    path('submissions/<int:pk>/grade/', views.grade, name='grade'),
    path('submissions/<int:pk>/download/', views.download, name='download'),
]
