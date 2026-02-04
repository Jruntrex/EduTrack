from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, StudyGroup, Subject, TeachingAssignment, EvaluationType, 
    StudentPerformance, AbsenceReason, 
    TimeSlot, ScheduleTemplate, Lesson,
    Classroom, GradingScale, GradeRule
)
from .forms import UserAdminForm

# Налаштовуємо відображення вашого кастомного юзера
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    add_form = UserAdminForm
    # Поля, які видно у списку
    list_display = ('email', 'full_name', 'role', 'group', 'is_staff')
    # Поля для фільтрації збоку
    list_filter = ('role', 'is_staff', 'is_active', 'group')
    # Поля, по яким можна шукати
    search_fields = ('email', 'full_name')
    # Порядок полів при редагуванні (Django специфіка)
    ordering = ('email',)
    
    # Конфігурація форми редагування
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Персональна інформація', {'fields': ('full_name', 'role', 'group')}),
        ('Права доступу', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    # Конфігурація форми створення
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'role', 'group', 'password', 'confirm_password'),
        }),
    )

# Реєструємо всі моделі
admin.site.register(User, UserAdmin)
admin.site.register(StudyGroup)
admin.site.register(Subject)
admin.site.register(TeachingAssignment)
admin.site.register(EvaluationType)
admin.site.register(ScheduleTemplate)
admin.site.register(Lesson)
admin.site.register(StudentPerformance)
admin.site.register(AbsenceReason)
admin.site.register(TimeSlot)
admin.site.register(Classroom)
admin.site.register(GradingScale)
admin.site.register(GradeRule)
