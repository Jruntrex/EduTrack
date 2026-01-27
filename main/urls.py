# main/urls.py

from django.urls import path

from . import views

urlpatterns = [
    # =========================
    # 1. АУТЕНТИФІКАЦІЯ
    # =========================
    path('', views.login_view, name='login'),
    path('login/', views.login_process, name='login_process'),
    path('logout/', views.logout_view, name='logout'),
    # =========================
    # 2. АДМІНІСТРУВАННЯ ТА ДАШБОРДИ
    # =========================
    path('admin/', views.admin_panel_view, name='admin_panel'),
    path('users/', views.users_list_view, name='users_list'),
    path('schedule/set/', views.set_weekly_schedule_view, name='set_weekly_schedule'),
    path('schedule/save/', views.save_schedule_changes, name='save_schedule'),
    # Управління Користувачами (CRUD)
    path('users/edit/<int:pk>/', views.user_edit_view, name='user_edit'),
    path('users/delete/<int:pk>/', views.user_delete_view, name='user_delete'),
    # Управління Групами (CRUD)
    path('groups/', views.groups_list_view, name='groups_list'),
    path('groups/add/', views.group_add_view, name='group_add'),
    path('groups/delete/<int:pk>/', views.group_delete_view, name='group_delete'),
    # Управління Предметами (CRUD)
    path('subjects/', views.subjects_list_view, name='subjects_list'),
    path('subjects/add/', views.subject_add_view, name='subject_add'),
    path('subjects/delete/<int:pk>/', views.subject_delete_view, name='subject_delete'),
    # =========================
    # 3. ЗВІТИ (CSV)
    # =========================
    path('admin/reports/', views.admin_reports_view, name='admin_reports'),
    path('admin/reports/rating/', views.report_rating_view, name='report_rating'),
    path('admin/reports/absences/', views.report_absences_view, name='report_absences'),
    path(
        'admin/reports/weekly_absences/',
        views.report_weekly_absences_view,
        name='report_weekly_absences',
    ),
    # =========================
    # 4. ВИКЛАДАЧ ТА ЖУРНАЛ
    # =========================
    path('teacher/', views.teacher_journal_view, name='teacher_journal'),
    path('teacher/save/', views.save_journal_entries, name='save_journal_entries'),
    # Управління типами оцінювання
    path('teacher/evaluation-types/', views.manage_evaluation_types_view, name='manage_evaluation_types'),
    path('teacher/evaluation-type/edit/<int:pk>/', views.evaluation_type_edit_view, name='edit_evaluation_type'),
    path('teacher/evaluation-type/delete/<int:pk>/', views.evaluation_type_delete_view, name='delete_evaluation_type'),
    path('api/evaluation-types/', views.get_evaluation_types_api, name='get_evaluation_types_api'),
    # =========================
    # 5. СТУДЕНТ
    # =========================
    path('student/grades/', views.student_grades_view, name='student_grades'),
    path('student/attendance/', views.student_attendance_view, name='student_attendance'),
]