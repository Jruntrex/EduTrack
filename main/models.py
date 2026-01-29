from django.db import models
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

    def __str__(self):
        return self.name

class CustomUserManager(BaseUserManager):
    """Менеджер для створення користувачів (потрібен для AbstractBaseUser)"""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email є обов\'язковим')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
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

    def __str__(self):
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

    def __str__(self):
        return self.name

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

    def __str__(self):
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

    def __str__(self):
        return f"{self.name} ({self.weight_percent}%)"

# ==========================================
# 3. РОЗКЛАД І ЖУРНАЛ
# ==========================================

class WeeklySchedule(models.Model):
    """
    Шаблон розкладу (щотижневий).
    """
    DAY_CHOICES = [
        (1, 'Понеділок'), (2, 'Вівторок'), (3, 'Середа'),
        (4, 'Четвер'), (5, 'П\'ятниця'), (6, 'Субота'), (7, 'Неділя')
    ]
    
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE, verbose_name="Дисципліна")
    day_of_week = models.IntegerField(choices=DAY_CHOICES, verbose_name="День тижня")
    lesson_number = models.PositiveSmallIntegerField(verbose_name="Номер пари")
    
    class Meta:
        db_table = 'weekly_schedule'
        unique_together = ('assignment', 'day_of_week', 'lesson_number')
        verbose_name = "Розклад"
        verbose_name_plural = "Розклад"

class LessonSession(models.Model):
    """
    КОНКРЕТНИЙ ПРОВЕДЕНИЙ УРОК.
    """
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE)
    date = models.DateField(verbose_name="Дата проведення")
    lesson_number = models.PositiveSmallIntegerField()
    
    evaluation_type = models.ForeignKey(EvaluationType, on_delete=models.PROTECT, verbose_name="Тип заняття")
    topic = models.CharField(max_length=255, blank=True, verbose_name="Тема заняття")

    class Meta:
        db_table = 'lesson_sessions'
        unique_together = ('assignment', 'date', 'lesson_number')
        ordering = ['-date', 'lesson_number']
        verbose_name = "Проведене заняття"
        verbose_name_plural = "Проведені заняття"

    def __str__(self):
        return f"{self.date} - {self.assignment.subject.name} ({self.evaluation_type.name})"

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

    def __str__(self):
        return self.code

class StudentPerformance(models.Model):
    """
    Єдиний запис про успішність студента на уроці.
    """
    lesson = models.ForeignKey(LessonSession, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    
    grade = models.DecimalField(
        max_digits=5, decimal_places=2, 
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)], 
        verbose_name="Оцінка"
    )
    
    absence = models.ForeignKey(AbsenceReason, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пропуск")
    
    comment = models.CharField(max_length=255, blank=True, verbose_name="Коментар")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_performance'
        unique_together = ('lesson', 'student')
        verbose_name = "Успішність студента"
        verbose_name_plural = "Успішність студентів"

    def clean(self):
        # Валідація: студент має належати до групи, яка вказана в уроці
        if self.student.group != self.lesson.assignment.group:
            raise ValidationError("Студент не належить до групи, для якої проводиться урок.")