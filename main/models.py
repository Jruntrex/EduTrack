from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password

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

class User(models.Model):
    """Єдина модель користувача"""
    ROLE_CHOICES = [
        ('admin', 'Адміністратор'),
        ('teacher', 'Викладач'),
        ('student', 'Студент'),
    ]

    full_name = models.CharField(max_length=255, verbose_name="ПІБ")
    email = models.EmailField(unique=True, verbose_name="Email")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, verbose_name="Роль")
    password_hash = models.CharField(max_length=255)

    # Студент прив'язаний до групи, викладачі/адміни - ні
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tbl_users'
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    def check_password(self, password):
        """Перевіряє, чи пароль збігається з збереженим хешем."""
        return check_password(password, self.password_hash)

    def set_password(self, password):
        """Встановлює пароль з хешуванням."""
        self.password_hash = make_password(password)

class Subject(models.Model):
    """
    Довідник предметів.
    Тут немає викладача, бо один предмет можуть читати 10 різних людей.
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
    Адмін створює запис: "Викладач Петренко читає Математику у групи КН-41".
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
    Викладач додає сюди: "Лекція (10%)", "Екзамен (40%)".
    Прив'язано до TeachingAssignment, тому у кожного викладача свої налаштування.
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
    Адмін заповнює, використовуючи вже створене призначення (TeachingAssignment).
    """
    DAY_CHOICES = [
        (1, 'Понеділок'), (2, 'Вівторок'), (3, 'Середа'),
        (4, 'Четвер'), (5, 'П\'ятниця'), (6, 'Субота'), (7, 'Неділя')
    ]
    
    # Використовуємо assignment, щоб точно знати предмет+викладача+групу
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
    Створюється автоматично (за розкладом) або вручну викладачем.
    Викладач обирає, що це було за заняття (EvaluationType).
    """
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.CASCADE)
    date = models.DateField(verbose_name="Дата проведення")
    lesson_number = models.PositiveSmallIntegerField()
    
    # Викладач вказує тип цього конкретного уроку (напр. "Сьогодні була Лабораторна")
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
    Може містити оцінку АБО пропуск, АБО і те і інше.
    """
    lesson = models.ForeignKey(LessonSession, on_delete=models.CASCADE, related_name='grades')
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    
    # Оцінка (nullable, бо може бути тільки пропуск)
    grade = models.DecimalField(
        max_digits=5, decimal_places=2, 
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)], 
        verbose_name="Оцінка"
    )
    
    # Пропуск (nullable, бо студент може бути присутнім)
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