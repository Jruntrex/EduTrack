from django.db import models
from typing import Optional, Any, List, Union
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# ==========================================
# 1. БАЗОВІ СУТНОСТІ (АДМІНІСТРАТИВНІ)
# ==========================================

class StudyGroup(models.Model):
    """Група студентів (напр. КН-41)"""
    name = models.CharField(max_length=50, unique=True, verbose_name="Назва групи")

    class Meta:
        db_table = 'study_groups'
        verbose_name = "Група"
        verbose_name_plural = "Групи"

    def __str__(self) -> str:
        return self.name

class CustomUserManager(BaseUserManager):
    """Менеджер для створення користувачів (потрібен для AbstractBaseUser)"""
    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: Any) -> 'User':
        if not email:
            raise ValueError('Email є обов\'язковим')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields: Any) -> 'User':
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin') # Адмін за замовчуванням
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Оновлена модель користувача з повною інтеграцією Django Auth"""
    ROLE_CHOICES = [
        ('admin', 'Адміністратор'),
        ('teacher', 'Викладач'),
        ('student', 'Студент'),
    ]

    email = models.EmailField(unique=True, verbose_name="Email")
    full_name = models.CharField(max_length=255, verbose_name="ПІБ")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student', verbose_name="Роль")
    
    # Студент прив'язаний до групи, викладачі/адміни - ні
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )

    # Технічні поля Django
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # Чи має доступ до адмінки
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email' # Логін через Email
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'tbl_users'
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.get_role_display()})"

class Subject(models.Model):
    """
    Довідник предметів.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва предмету")
    description = models.TextField(blank=True, verbose_name="Опис")

    class Meta:
        db_table = 'subjects'
        verbose_name = "Предмет"
        verbose_name_plural = "Предмети"

    def __str__(self) -> str:
        return self.name

class Classroom(models.Model):
    """Аудиторія (напр. 305-А)"""
    name = models.CharField(max_length=50, unique=True, verbose_name="Назва/Номер")
    building = models.CharField(max_length=100, blank=True, verbose_name="Корпус")
    capacity = models.PositiveIntegerField(null=True, blank=True, verbose_name="Місткість")

    class Meta:
        db_table = 'classrooms'
        verbose_name = "Аудиторія"
        verbose_name_plural = "Аудиторії"

    def __str__(self) -> str:
        return f"{self.name} ({self.building})" if self.building else self.name

class GradingScale(models.Model):
    """Шкала оцінювання (напр. 100-бальна, ЄКТС)"""
    name = models.CharField(max_length=50, unique=True, verbose_name="Назва шкали")

    class Meta:
        db_table = 'grading_scales'
        verbose_name = "Шкала оцінювання"
        verbose_name_plural = "Шкали оцінювання"

    def __str__(self) -> str:
        return self.name

class GradeRule(models.Model):
    """Правила переведення балів у оцінки (напр. 90+ = Відмінно)"""
    scale = models.ForeignKey(GradingScale, on_delete=models.CASCADE, related_name='rules')
    label = models.CharField(max_length=50, verbose_name="Оцінка (словом/буквою)")
    min_points = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Мінімальний бал")

    class Meta:
        db_table = 'grade_rules'
        ordering = ['-min_points']
        verbose_name = "Правило оцінювання"
        verbose_name_plural = "Правила оцінювання"

    def __str__(self) -> str:
        return f"{self.scale.name}: {self.label} (>= {self.min_points})"

# ==========================================
# 2. НАВЧАЛЬНИЙ ПРОЦЕС (ЗВ'ЯЗКИ)
# ==========================================

class TeachingAssignment(models.Model):
    """
    ПРИЗНАЧЕННЯ: Головна таблиця зв'язку.
    """
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'teacher'},
        verbose_name="Викладач",
    )
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, verbose_name="Група")

    class Meta:
        db_table = 'teaching_assignments'
        unique_together = ('subject', 'teacher', 'group')
        verbose_name = "Навантаження викладача"
        verbose_name_plural = "Навантаження викладачів"

    def __str__(self) -> str:
        return f"{self.subject.name} - {self.group.name} ({self.teacher.full_name})"

class EvaluationType(models.Model):
    """
    КОНФІГУРАЦІЯ ОЦІНЮВАННЯ.
    """
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE, related_name='evaluation_types')
    name = models.CharField(max_length=50, verbose_name="Тип заняття (Лекція/Практика)")
    weight_percent = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=0, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Вплив на оцінку (%)"
    )

    class Meta:
        db_table = 'evaluation_types'
        verbose_name = "Тип оцінювання"
        verbose_name_plural = "Типи оцінювання"

    def __str__(self) -> str:
        return f"{self.name} ({self.weight_percent}%)"

class TimeSlot(models.Model):
    """Часові слоти для пар (Дзвінки)"""
    lesson_number = models.PositiveSmallIntegerField(unique=True, verbose_name="Номер пари")
    start_time = models.TimeField(verbose_name="Початок")
    end_time = models.TimeField(verbose_name="Кінець")

    class Meta:
        db_table = 'time_slots'
        ordering = ['start_time']
        verbose_name = "Розклад дзвінків"
        verbose_name_plural = "Розклад дзвінків"

    def __str__(self) -> str:
        return f"{self.lesson_number} пара ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"

    def duration_minutes(self) -> int:
        # Допоміжний метод для розрахунку довжини на графіку
        t1 = self.start_time
        t2 = self.end_time
        return (t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)

# ==========================================
# 3. РОЗКЛАД І ЖУРНАЛ (TIMELORD EDITION)
# ==========================================

class ScheduleTemplate(models.Model):
    """
    Шаблон розкладу (правила).
    
    MIGRATION NOTE: teaching_assignment - новий зв'язок (від 04.02.2026)
    Старі поля (subject, teacher, group) залишені для міграції.
    """
    # НОВИЙ ЗВ'ЯЗОК: Single Source of Truth
    teaching_assignment = models.ForeignKey(
        TeachingAssignment,
        on_delete=models.CASCADE,
        null=True,  # Тимчасово nullable для міграції
        blank=True,
        related_name='schedule_templates',
        verbose_name="Навантаження викладача",
        help_text="Зв'язок з призначенням викладача (subject+teacher+group)"
    )
    
    # СТАРІ ПОЛЯ (для зворотної сумісності під час міграції)
    # TODO: Видалити після завершення міграції даних
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, verbose_name="Група")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'teacher'},
        verbose_name="Викладач"
    )
    
    # РОЗКЛАД
    day_of_week = models.IntegerField(
        choices=[(1, 'Пн'), (2, 'Вт'), (3, 'Ср'), (4, 'Чт'), (5, 'Пт'), (6, 'Сб'), (7, 'Нд')],
        verbose_name="День тижня"
    )
    lesson_number = models.PositiveSmallIntegerField(default=1, verbose_name="Номер пари")
    start_time = models.TimeField(verbose_name="Час початку")
    duration_minutes = models.IntegerField(default=80, verbose_name="Тривалість (хв)")
    classroom = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Аудиторія")
    
    valid_from = models.DateField(auto_now_add=True, verbose_name="Діє з")
    valid_to = models.DateField(null=True, blank=True, verbose_name="Діє до")

    class Meta:
        db_table = 'schedule_templates'
        verbose_name = "Шаблон розкладу"
        verbose_name_plural = "Шаблони розкладу"

    def __str__(self) -> str:
        return f"{self.get_day_of_week_display()} {self.start_time} - {self.subject.name} ({self.group.name})"

class Lesson(models.Model):
    """
    Конкретний урок у календарі.
    """
    group = models.ForeignKey(StudyGroup, on_delete=models.CASCADE, verbose_name="Група")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, verbose_name="Предмет")
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'role': 'teacher'},
        verbose_name="Викладач"
    )
    
    date = models.DateField(verbose_name="Дата")
    start_time = models.TimeField(verbose_name="Час початку")
    end_time = models.TimeField(verbose_name="Час закінчення")
    
    topic = models.CharField(max_length=255, blank=True, verbose_name="Тема заняття")
    classroom = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Аудиторія")
    max_points = models.PositiveIntegerField(default=5, verbose_name="Макс. балів")
    evaluation_type = models.ForeignKey(EvaluationType, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Тип заняття")
    
    template_source = models.ForeignKey(
        ScheduleTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Джерело (шаблон)"
    )

    class Meta:
        db_table = 'lessons'
        unique_together = ('group', 'date', 'start_time')
        ordering = ['-date', 'start_time']
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"

    def __str__(self) -> str:
        return f"{self.date} {self.start_time} - {self.subject.name}"

# ==========================================
# 4. УСПІШНІСТЬ СТУДЕНТА
# ==========================================

class AbsenceReason(models.Model):
    """Довідник типів пропусків (Н, Хв, тощо)"""
    code = models.CharField(max_length=5, unique=True) # Н, Б, В
    description = models.CharField(max_length=100)
    is_respectful = models.BooleanField(default=False, verbose_name="Поважна причина")

    class Meta:
        db_table = 'absence_reasons'
        verbose_name = "Причина пропуску"
        verbose_name_plural = "Причини пропусків"

    def __str__(self) -> str:
        return self.code

class StudentPerformance(models.Model):
    """
    Єдиний запис про успішність студента на уроці.
    """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    
    earned_points = models.DecimalField(
        max_digits=5, decimal_places=2, 
        null=True, blank=True,
        verbose_name="Набрані бали"
    )
    
    absence = models.ForeignKey(AbsenceReason, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пропуск")
    
    comment = models.CharField(max_length=255, blank=True, verbose_name="Коментар")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_performance'
        unique_together = ('lesson', 'student')
        verbose_name = "Успішність студента"
        verbose_name_plural = "Успішність студентів"

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.lesson.subject.name} ({self.lesson.date})"

    def clean(self) -> None:
        # Валідація: студент має належати до групи, яка вказана в уроці
        if self.student.group != self.lesson.group:
            raise ValidationError("Студент не належить до групи, для якої проводиться урок.")
