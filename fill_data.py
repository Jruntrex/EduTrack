import os
import django
import random
from datetime import datetime, timedelta

# Налаштування Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (
    User, StudyGroup, Subject, TeachingAssignment, 
    WeeklySchedule, LessonSession, StudentPerformance, 
    AbsenceReason, EvaluationType
)
from django.contrib.auth.hashers import make_password

# --- ДАНІ ДЛЯ ГЕНЕРАЦІЇ ---
FIRST_NAMES = ["Олександр", "Максим", "Іван", "Артем", "Дмитро", "Андрій", "Богдан", "Владислав", "Марія", "Анна", "Софія", "Дарина", "Вікторія", "Надія", "Олена", "Юлія"]
LAST_NAMES = ["Шевченко", "Бойко", "Коваленко", "Бондаренко", "Ткаченко", "Кравчук", "Козак", "Олійник", "Шевчук", "Поліщук", "Лисенко", "Мельник", "Павленко"]

TEACHERS_DATA = [
    ("Сергій", "Петренко"), ("Олена", "Василенко"), ("Микола", "Гнатюк"),
    ("Ірина", "Савченко"), ("Андрій", "Дорошенко"), ("Світлана", "Кузьменко"),
    ("Олег", "Сидоренко"), ("Марина", "Романенко"), ("Віктор", "Захарченко"), ("Наталія", "Кравченко")
]

SUBJECTS_LIST = [
    "Об'єктно-орієнтоване програмування", "Бази даних", "Вища математика", 
    "Алгоритми та структури даних", "Веб-технології", "Комп'ютерні мережі",
    "Операційні системи", "Англійська мова (IT)", "Філософія", "Кібербезпека"
]

def generate_email_pass(first_name, last_name, suffix=""):
    # Транслітерація для email (спрощена)
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ie', 'ж': 'zh', 'з': 'z',
        'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p',
        'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ь': '', 'ю': 'iu', 'я': 'ia',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E', 'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z',
        'И': 'Y', 'І': 'I', 'Ї': 'Yi', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P',
        'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
        'Ь': '', 'Ю': 'Yu', 'Я': 'Ya'
    }
    raw_login = "".join([translit.get(c, c) for c in last_name.lower()])
    if suffix:
        raw_login += f"_{suffix}"
    
    email = f"{raw_login}@gmail.com"
    password = raw_login # Пароль такий самий як частина email до @
    return email, password

def clear_db():
    print("--- 1. Очищення бази даних ---")
    StudentPerformance.objects.all().delete()
    LessonSession.objects.all().delete()
    WeeklySchedule.objects.all().delete()
    EvaluationType.objects.all().delete() # Важливо очистити типи
    TeachingAssignment.objects.all().delete()
    User.objects.all().delete()
    Subject.objects.all().delete()
    StudyGroup.objects.all().delete()
    AbsenceReason.objects.all().delete()
    print("База чиста.")

def populate():
    # --- СТАТИЧНІ ДАНІ ---
    print("--- 2. Створення довідників ---")
    abs_n = AbsenceReason.objects.create(code='Н', description='Неявка', is_respectful=False)
    abs_p = AbsenceReason.objects.create(code='ПП', description='Поважна причина', is_respectful=True)
    abs_h = AbsenceReason.objects.create(code='ХВ', description='Хвороба', is_respectful=True)
    absence_choices = [abs_n, abs_n, abs_n, abs_p, abs_h] # Н - частіше

    groups = [StudyGroup.objects.create(name=g) for g in ['КН-11', 'КН-12', 'ПП-21', 'КІ-31']]
    subjects = [Subject.objects.create(name=s) for s in SUBJECTS_LIST]

    # --- КОРИСТУВАЧІ ---
    print("--- 3. Створення користувачів (Admin, Teachers, Students) ---")
    
    # Адмін
    User.objects.create(
        full_name="Головний Адмін",
        email="admin@gmail.com",
        password_hash=make_password("admin"),
        role="admin"
    )

    # Викладачі (10)
    teachers = []
    for fname, lname in TEACHERS_DATA:
        email, raw_pass = generate_email_pass(fname, lname)
        t = User.objects.create(
            full_name=f"{lname} {fname}",
            email=email,
            password_hash=make_password(raw_pass),
            role="teacher"
        )
        teachers.append(t)
        print(f"   [Викладач] {t.full_name} -> {email} / {raw_pass}")

    # Студенти (40 - по 10 в групу)
    students = []
    count = 1
    for group in groups:
        for _ in range(10):
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            # Додаємо ID групи до логіну, щоб уникнути дублікатів (шевченко_кн11)
            suffix = group.name.lower().replace("-", "") + f"{random.randint(1,99)}"
            email, raw_pass = generate_email_pass(fname, lname, suffix)
            
            s = User.objects.create(
                full_name=f"{lname} {fname}",
                email=email,
                password_hash=make_password(raw_pass),
                role="student",
                group=group
            )
            students.append(s)
            count += 1
    print(f"   Створено {len(students)} студентів.")

    # --- НАВАНТАЖЕННЯ ТА ТИПИ ОЦІНЮВАННЯ ---
    print("--- 4. Розподіл предметів та налаштування типів оцінювання ---")
    assignments = []
    
    # Кожній групі даємо 5-6 предметів
    for group in groups:
        group_subjects = random.sample(subjects, 6)
        for sub in group_subjects:
            teacher = random.choice(teachers)
            assign = TeachingAssignment.objects.create(
                subject=sub, teacher=teacher, group=group
            )
            assignments.append(assign)

            # ВАЖЛИВО: Створюємо типи оцінювання для цього призначення!
            # Без цього ми не зможемо створити LessonSession
            EvaluationType.objects.create(assignment=assign, name="Лекція", weight_percent=10)
            EvaluationType.objects.create(assignment=assign, name="Практична", weight_percent=30)
            EvaluationType.objects.create(assignment=assign, name="Лабораторна", weight_percent=40)
            EvaluationType.objects.create(assignment=assign, name="Семінар", weight_percent=20)

    # --- РОЗКЛАД ---
    print("--- 5. Генерація тижневого розкладу ---")
    # Для кожної групи заповнюємо Пн-Пт по 3-4 пари
    for group in groups:
        group_assignments = TeachingAssignment.objects.filter(group=group)
        assign_list = list(group_assignments)
        
        if not assign_list: continue

        for day in range(5): # 0=Пн ... 4=Пт
            # 3 або 4 пари на день
            num_lessons = random.randint(3, 4)
            # Перемішуємо предмети, щоб не було підряд однакових (спрощено)
            daily_subjects = random.sample(assign_list * 2, num_lessons) # Беремо із запасом
            
            for i in range(num_lessons):
                WeeklySchedule.objects.create(
                    assignment=daily_subjects[i],
                    day_of_week=day, # 0..6 (в моделі IntegerField з choices)
                    lesson_number=i + 1 # Пари 1..4
                )

    # --- ІСТОРІЯ (СЕСІЇ ТА ОЦІНКИ) ---
    print("--- 6. Заповнення журналу за 3 тижні ---")
    today = datetime.now().date()
    # 21 день назад
    start_date = today - timedelta(days=21)
    
    # Проходимо по кожному дню від start_date до today
    current_date = start_date
    while current_date <= today:
        weekday = current_date.weekday() # 0=Mon
        
        if weekday < 5: # Якщо будній день
            # Знаходимо всі записи в розкладі на цей день тижня
            schedules = WeeklySchedule.objects.filter(day_of_week=weekday)
            
            for sch in schedules:
                # Отримуємо доступні типи оцінювання для цього предмета
                # (ми їх створили на етапі 4)
                eval_types = sch.assignment.evaluation_types.all()
                if not eval_types.exists():
                    continue
                
                # Випадково обираємо, що це було за заняття (Лекція чи Практика...)
                selected_type = random.choice(eval_types)
                
                # Створюємо проведений урок
                session = LessonSession.objects.create(
                    assignment=sch.assignment,
                    date=current_date,
                    lesson_number=sch.lesson_number,
                    evaluation_type=selected_type, # <--- ТУТ БУЛА ПОМИЛКА, ТЕПЕР FK
                    topic=f"Тема уроку №{random.randint(1,20)} по {sch.assignment.subject.name}"
                )

                # Ставимо оцінки студентам групи
                students_in_group = sch.assignment.group.students.all()
                
                for student in students_in_group:
                    roll = random.random()
                    
                    if roll < 0.1: # 10% пропуск
                        StudentPerformance.objects.create(
                            lesson=session,
                            student=student,
                            absence=random.choice(absence_choices)
                        )
                    elif roll < 0.8: # 70% оцінка + присутність
                        grade_val = random.randint(5, 12) # 12-бальна система
                        # Трохи реалізму: на лекціях оцінки рідше, на практиках частіше
                        if "Лекція" in selected_type.name and random.random() > 0.3:
                            continue # На лекції часто просто сидять
                            
                        StudentPerformance.objects.create(
                            lesson=session,
                            student=student,
                            grade=grade_val
                        )
                    # 20% просто був присутній без оцінки (не створюємо запис або створюємо пустий, залежить від логіки. Тут не створюємо)

        current_date += timedelta(days=1)

    print("\nГОТОВО! БД успішно заповнена.")
    print("Приклади викладачів (пароль такий же як логін):")
    for t in User.objects.filter(role='teacher')[:3]:
        print(f" - {t.email}")
    
    print("Приклади студентів (пароль такий же як логін):")
    for s in User.objects.filter(role='student')[:3]:
        print(f" - {s.email}")

if __name__ == "__main__":
    clear_db()
    populate()