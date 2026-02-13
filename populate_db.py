import os
import django
import random
import unicodedata
from datetime import date, timedelta, datetime, time

# Налаштування оточення Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (
    User, StudyGroup, Subject, TeachingAssignment, 
    EvaluationType, ScheduleTemplate, Lesson, 
    StudentPerformance, AbsenceReason, Classroom,
    TimeSlot, GradingScale, GradeRule
)
from django.contrib.auth import get_user_model

User = get_user_model()

def transliterate(text):
    """Проста транслітерація для генерації email."""
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ye',
        'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya'
    }
    res = ''.join(mapping.get(c.lower(), c) for c in text)
    return res.replace("'", "").replace(" ", "_")

def create_initial_data():
    print("🧹 Очищення бази даних...")
    # Очищуємо все, крім суперкористувачів
    models_to_clean = [
        StudentPerformance, Lesson, ScheduleTemplate, EvaluationType, 
        TeachingAssignment, Subject, StudyGroup, AbsenceReason, 
        Classroom, TimeSlot, GradingScale, GradeRule
    ]
    for model in models_to_clean:
        model.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    print("✅ База очищена.")

    # 1. Причини пропусків (згідно з AbsenceCode у constants.py)
    reasons_data = [
        ('Н', 'Неявка', False),
        ('Б', 'Хвороба', True),
        ('ПП', 'Поважна причина', True),
        ('В', 'Відпустка', True),
    ]
    reasons = [AbsenceReason.objects.create(code=c, description=d, is_respectful=r) for c, d, r in reasons_data]

    # 2. Групи (5 груп)
    group_names = ["КН-41", "КН-42", "ІПЗ-11", "ІПЗ-12", "СS-21"]
    groups = [StudyGroup.objects.create(name=name) for name in group_names]

    # 3. Аудиторії та Часові слоти (згідно з DEFAULT_TIME_SLOTS)
    classrooms = [Classroom.objects.create(name=f"{r}0{i}", capacity=30) for r in [1, 2] for i in range(1, 6)]
    
    # Створюємо 5 пар на день
    time_data = [
        (1, time(8, 30), time(10, 0)),
        (2, time(10, 0), time(11, 30)),
        (3, time(11, 40), time(13, 10)),
        (4, time(13, 30), time(15, 0)),
        (5, time(15, 0), time(16, 30)),
    ]
    time_slots = [TimeSlot.objects.create(lesson_number=n, start_time=s, end_time=e) for n, s, e in time_data]

    # 4. Предмети
    subject_names = [
        "Вища математика", "Об'єктно-орієнтоване програмування", "Бази даних", 
        "Веб-технології", "Алгоритми", "Комп'ютерні мережі", "Архітектура ЕОМ", "Фізика"
    ]
    subjects = [Subject.objects.create(name=name) for name in subject_names]

    # 5. Викладачі (10 осіб, 1/4 від 40 студентів)
    t_last_names = ["Мельник", "Шевченко", "Бойко", "Ткаченко", "Коваленко", "Бондар", "Олійник", "Вовк", "Поліщук", "Кравченко"]
    teachers = []
    for ln in t_last_names:
        prefix = f"t_{transliterate(ln)}"
        email = f"{prefix}@gmail.com"
        user = User.objects.create_user(
            email=email,
            password=prefix, # Пароль = назва до @
            full_name=f"Професор {ln}",
            role='teacher'
        )
        teachers.append(user)

    # 6. Студенти (40 осіб)
    s_last_names = [
        "Іваненко", "Петренко", "Сидоренко", "Кушнір", "Лисенко", "Руденко", "Мороз", "Харченко", 
        "Василенко", "Павленко", "Савченко", "Козак", "Жук", "Кот", "Сорока", "Ворона", 
        "Гончар", "Швець", "Кравець", "Ткач", "Коваль", "Гармаш", "Скляр", "Мельниченко",
        "Білоус", "Чорний", "Білий", "Сизий", "Мазур", "Дуб", "Береза", "Явір", 
        "Гайдай", "Довженко", "Стус", "Костенко", "Тичина", "Рильський", "Сосюра", "Гончаренко"
    ]
    students = []
    for i, ln in enumerate(s_last_names):
        prefix = f"s_{transliterate(ln)}_{i}"
        user = User.objects.create_user(
            email=f"{prefix}@gmail.com",
            password=prefix,
            full_name=f"Студент {ln}",
            role='student',
            group=groups[i % len(groups)]
        )
        students.append(user)

    # 7. Призначення та типи оцінювання
    assignments = []
    for group in groups:
        group_subjects = random.sample(subjects, 6) # Кожна група має 6 предметів
        for subj in group_subjects:
            teacher = random.choice(teachers)
            assign = TeachingAssignment.objects.create(teacher=teacher, subject=subj, group=group)
            assignments.append(assign)
            # Додаємо вагові коефіцієнти
            EvaluationType.objects.create(assignment=assign, name="Лекція", weight_percent=20)
            EvaluationType.objects.create(assignment=assign, name="Практична", weight_percent=50)
            EvaluationType.objects.create(assignment=assign, name="Лабораторна", weight_percent=30)

    # 8. Розклад (Full Schedule)
    templates = []
    for group in groups:
        group_assigns = [a for a in assignments if a.group == group]
        for day in range(1, 6): # Пн-Пт
            daily_subjects = random.sample(group_assigns, 4) # 4 пари щодня
            for i, assign in enumerate(daily_subjects):
                slot = time_slots[i]
                templates.append(ScheduleTemplate.objects.create(
                    teaching_assignment=assign,
                    group=group,
                    subject=assign.subject,
                    teacher=assign.teacher,
                    day_of_week=day,
                    lesson_number=slot.lesson_number,
                    start_time=slot.start_time,
                    duration_minutes=80,
                    classroom=random.choice(classrooms),
                    valid_from="2026-01-01"
                ))

    # 9. Генерація уроків та оцінок за 2 місяці (60 днів)
    today = date.today()
    start_date = today - timedelta(days=60)
    current_date = start_date
    
    print(f"⏳ Генерація даних з {start_date} по {today}...")
    
    while current_date <= today:
        weekday = current_date.weekday() + 1
        if weekday <= 5: # Робочі дні
            day_templates = [t for t in templates if t.day_of_week == weekday]
            for tmpl in day_templates:
                eval_type = tmpl.teaching_assignment.evaluation_types.order_by('?').first()
                lesson = Lesson.objects.create(
                    group=tmpl.group, subject=tmpl.subject, teacher=tmpl.teacher,
                    date=current_date, start_time=tmpl.start_time,
                    end_time=(datetime.combine(current_date, tmpl.start_time) + timedelta(minutes=80)).time(),
                    evaluation_type=eval_type, max_points=100
                )
                
                # Заповнюємо успішність для кожного студента групи
                group_students = [s for s in students if s.group == tmpl.group]
                for student in group_students:
                    dice = random.random()
                    if dice < 0.1: # 10% пропусків
                        StudentPerformance.objects.create(lesson=lesson, student=student, absence=reasons[0])
                    elif dice < 0.8: # 70% отримали оцінку
                        StudentPerformance.objects.create(
                            lesson=lesson, student=student, 
                            earned_points=random.randint(60, 100),
                            comment="Автоматично згенеровано"
                        )
        current_date += timedelta(days=1)

    print("\n✅ Успішно! Створено:")
    print(f"- 5 груп та 8 предметів")
    print(f"- 10 викладачів та 40 студентів")
    print(f"- Повний розклад та історія за 60 днів")
    print("\n🔑 ПРИКЛАД ВХОДУ:")
    print(f"Викладач: {teachers[0].email} / Пароль: {transliterate(t_last_names[0])}")
    print(f"Студент: {students[0].email} / Пароль: s_{transliterate(s_last_names[0])}_0")

if __name__ == '__main__':
    create_initial_data()