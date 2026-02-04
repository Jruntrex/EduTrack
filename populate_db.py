import os
import django
import random
from datetime import date, timedelta, datetime

# Налаштування оточення Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (
    User, StudyGroup, Subject, TeachingAssignment, 
    EvaluationType, ScheduleTemplate, Lesson, 
    StudentPerformance, AbsenceReason
)
from django.contrib.auth import get_user_model

User = get_user_model()

def create_initial_data():
    print("🧹 Очищення старої бази...")
    # Видаляємо дані в правильному порядку
    StudentPerformance.objects.all().delete()
    Lesson.objects.all().delete()
    ScheduleTemplate.objects.all().delete()
    EvaluationType.objects.all().delete()
    TeachingAssignment.objects.all().delete()
    Subject.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete() # Залишаємо адміна
    StudyGroup.objects.all().delete()
    AbsenceReason.objects.all().delete()

    print("✅ База очищена.")

    # --- 1. Створення причин пропусків ---
    reasons = [
        AbsenceReason(code='Н', description='Неявка', is_respectful=False),
        AbsenceReason(code='Хв', description='Хвороба', is_respectful=True),
        AbsenceReason(code='ПП', description='Поважна причина', is_respectful=True),
    ]
    AbsenceReason.objects.bulk_create(reasons)
    print("✅ Причини пропусків створені.")

    # --- 2. Створення груп ---
    group_kn = StudyGroup.objects.create(name="КН-41")
    group_it = StudyGroup.objects.create(name="IT-12")
    groups = [group_kn, group_it]
    print(f"✅ Створено груп: 2")

    # --- 3. Створення предметів ---
    subjects_data = [
        "Вища математика", "Об'єктно-орієнтоване програмування", 
        "Філософія", "Іноземна мова", "Фізика", 
        "Бази даних", "Мережі"
    ]
    subjects = [Subject.objects.create(name=name) for name in subjects_data]
    print(f"✅ Створено предметів: {len(subjects)}")

    # --- 4. Створення викладачів ---
    # Формат: name1@gmail.com / name
    teacher_names = ["damian", "olena", "igor", "maryna", "petro"]
    teachers = []
    for name in teacher_names:
        user = User.objects.create_user(
            email=f"{name}1@gmail.com",
            password=name,
            full_name=f"{name.capitalize()} Teacher",
            role='teacher'
        )
        teachers.append(user)
    print(f"✅ Створено викладачів: {len(teachers)}")

    # --- 5. Створення студентів ---
    # Формат: name2@gmail.com / name
    student_names = ["alex", "bob", "charity", "david", "eva", "frank", "grace", "helen", "ivan", "julia"]
    students = []
    for i, name in enumerate(student_names):
        group = groups[i % 2]
        user = User.objects.create_user(
            email=f"{name}2@gmail.com",
            password=name,
            full_name=f"{name.capitalize()} Student",
            role='student',
            group=group
        )
        students.append(user)
    print(f"✅ Створено студентів: {len(students)}")

    # --- 6. Призначення предметів ---
    # 2 викладача мають по 2 предмети
    # 2 викладача мають один і той самий предмет (для тесту)
    
    # damian: Математика, ООП
    # olena: Математика (з damian), Філософія
    # igor: Фізика
    # maryna: Бази даних
    # petro: Мережі, Іноземна мова

    assignments_config = [
        (teachers[0], subjects[0], groups[0]), # damian - Математика (КН-41)
        (teachers[0], subjects[1], groups[1]), # damian - ООП (IT-12)
        (teachers[1], subjects[0], groups[1]), # olena - Математика (IT-12) - той самий предмет
        (teachers[1], subjects[2], groups[0]), # olena - Філософія (КН-41)
        (teachers[2], subjects[4], groups[0]), # igor - Фізика (КН-41)
        (teachers[3], subjects[5], groups[1]), # maryna - Бази даних (IT-12)
        (teachers[4], subjects[6], groups[0]), # petro - Мережі (КН-41)
        (teachers[4], subjects[3], groups[1]), # petro - Англійська (IT-12)
    ]

    assignments = []
    for t, s, g in assignments_config:
        assign = TeachingAssignment.objects.create(teacher=t, subject=s, group=g)
        assignments.append(assign)
        # Типи оцінювання
        EvaluationType.objects.create(assignment=assign, name="Лекція", weight_percent=30)
        EvaluationType.objects.create(assignment=assign, name="Практична", weight_percent=70)

    print("✅ Навантаження та типи оцінювання створені.")

    # --- 7. Створення шаблонів розкладу (ScheduleTemplate) ---
    templates = [
        # Понеділок (КН-41)
        ScheduleTemplate.objects.create(
            group=group_kn, subject=subjects[0], teacher=teachers[0],
            day_of_week=1, start_time="08:30", duration_minutes=90,
            valid_from="2026-02-01"
        ),
        # Вівторок (IT-12)
        ScheduleTemplate.objects.create(
            group=group_it, subject=subjects[1], teacher=teachers[0],
            day_of_week=2, start_time="10:05", duration_minutes=90,
            valid_from="2026-02-01"
        ),
    ]
    print("✅ Шаблони розкладу створені.")

    # --- 8. Генерація уроків та оцінок ---
    today = date.today()
    start_date = today - timedelta(days=14) # 2 тижні історії
    
    print(f"⏳ Генерація уроків з {start_date} по {today}...")

    current_date = start_date
    while current_date <= today:
        weekday = current_date.weekday() + 1
        day_templates = ScheduleTemplate.objects.filter(day_of_week=weekday)
        
        for tmpl in day_templates:
            # Створюємо урок
            start_dt = datetime.combine(current_date, tmpl.start_time)
            end_dt = start_dt + timedelta(minutes=tmpl.duration_minutes)
            
            # Шукаємо тип оцінювання
            eval_type = EvaluationType.objects.filter(
                assignment__subject=tmpl.subject, 
                assignment__group=tmpl.group
            ).first()

            lesson = Lesson.objects.create(
                group=tmpl.group,
                subject=tmpl.subject,
                teacher=tmpl.teacher,
                date=current_date,
                start_time=tmpl.start_time,
                end_time=end_dt.time(),
                template_source=tmpl,
                topic=f"Тема від {current_date}",
                evaluation_type=eval_type
            )

            # Ставимо оцінки
            group_students = [s for s in students if s.group == tmpl.group]
            for student in group_students:
                dice = random.randint(1, 100)
                if dice <= 15: # Н
                    StudentPerformance.objects.create(
                        lesson=lesson, 
                        student=student, 
                        absence=AbsenceReason.objects.get(code='Н')
                    )
                elif dice <= 70: # Оцінка
                    StudentPerformance.objects.create(
                        lesson=lesson, 
                        student=student, 
                        grade=random.choice([8, 10, 11, 12])
                    )

        current_date += timedelta(days=1)

    print("✅ База успішно наповнена!")
    print("\n--- TEST CREDENTIALS ---")
    print("Teacher: damian1@gmail.com / damian")
    print("Student: alex2@gmail.com / alex")

if __name__ == '__main__':
    create_initial_data()