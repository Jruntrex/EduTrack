# main/admin.py

from django.contrib import admin
from .models import (
    StudyGroup, User, Subject, AbsenceReason, 
    TeachingAssignment, EvaluationType, 
    WeeklySchedule, LessonSession, StudentPerformance
)

# =========================
# РЕЄСТРАЦІЯ ОСНОВНИХ МОДЕЛЕЙ
# =========================

@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(AbsenceReason)
class AbsenceReasonAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'is_respectful')
    list_filter = ('is_respectful',)

# =========================
# РОЗШИРЕНІ НАЛАШТУВАННЯ
# =========================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'role', 'group', 'created_at')
    list_filter = ('role', 'group')
    search_fields = ('full_name', 'email')
    readonly_fields = ('created_at',)

@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('subject', 'teacher', 'group')
    list_filter = ('group', 'teacher', 'subject')
    search_fields = ('subject__name', 'teacher__full_name')

@admin.register(EvaluationType)
class EvaluationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'assignment', 'weight_percent')
    list_filter = ('assignment',)

@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'day_of_week', 'lesson_number')
    list_filter = ('day_of_week', 'assignment__group')
    search_fields = ('assignment__subject__name',)

@admin.register(LessonSession)
class LessonSessionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'date', 'lesson_number', 'evaluation_type', 'topic')
    list_filter = ('date', 'assignment__group', 'evaluation_type')
    search_fields = ('topic', 'assignment__subject__name')
    readonly_fields = ('date',)

@admin.register(StudentPerformance)
class StudentPerformanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'lesson', 'grade', 'absence', 'updated_at')
    list_filter = ('lesson__date', 'absence', 'student__group')
    search_fields = ('student__full_name', 'lesson__topic')
    readonly_fields = ('updated_at',)