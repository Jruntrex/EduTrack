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

# ModelAdmin для розкладу - забезпечує правильне збереження
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ('get_group', 'get_day', 'lesson_number', 'get_subject', 'get_teacher', 'start_time', 'classroom')
    list_filter = ('group', 'day_of_week', 'subject', 'teacher')
    search_fields = ('group__name', 'subject__name', 'teacher__full_name')
    
    fieldsets = (
        ('Основна інформація', {
            'fields': ('group', 'day_of_week', 'lesson_number')
        }),
        ('Предмет та викладач', {
            'fields': ('subject', 'teacher', 'teaching_assignment')
        }),
        ('Розклад', {
            'fields': ('start_time', 'duration_minutes', 'classroom')
        }),
        ('Дійсність', {
            'fields': ('valid_from', 'valid_to')
        }),
    )
    
    # Автоматично встановлюємо readonly для дати створення
    readonly_fields = ('valid_from',)
    
    def get_group(self, obj):
        return obj.group.name
    get_group.short_description = 'Група'
    
    def get_day(self, obj):
        return obj.get_day_of_week_display()
    get_day.short_description = 'День'
    
    def get_subject(self, obj):
        return obj.subject.name
    get_subject.short_description = 'Предмет'
    
    def get_teacher(self, obj):
        return obj.teacher.full_name if obj.teacher else '—'
    get_teacher.short_description = 'Викладач'
    
    def save_model(self, request, obj, form, change):
        """Переопалювання save для завдяння викладача через teaching_assignment"""
        # При редагуванні в адміні, якщо викладач змінений, оновлюємо teaching_assignment
        if obj.teacher and obj.subject and obj.group:
            obj.teaching_assignment, _ = TeachingAssignment.objects.get_or_create(
                subject=obj.subject,
                teacher=obj.teacher,
                group=obj.group
            )
        super().save_model(request, obj, form, change)

# Реєструємо всі моделі
admin.site.register(User, UserAdmin)
admin.site.register(StudyGroup)
admin.site.register(Subject)
admin.site.register(TeachingAssignment)
admin.site.register(EvaluationType)
admin.site.register(ScheduleTemplate, ScheduleTemplateAdmin)
admin.site.register(Lesson)
admin.site.register(StudentPerformance)
admin.site.register(AbsenceReason)
admin.site.register(TimeSlot)
admin.site.register(Classroom)
admin.site.register(GradingScale)
admin.site.register(GradeRule)
