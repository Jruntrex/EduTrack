# pyright: reportGeneralTypeIssues=false
# pyright: reportMissingImports=false
import os
import sys
import django  # type: ignore[import]
import random
from datetime import date, timedelta, datetime, time

# Додаємо кореневу директорію проекту до sys.path, щоб IDE знаходив модулі
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Налаштування оточення Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (  # type: ignore[import]
    User, StudyGroup, Subject, TeachingAssignment,
    EvaluationType, ScheduleTemplate, Lesson,
    StudentPerformance, AbsenceReason, Classroom,
    TimeSlot, GradingScale, GradeRule
)
from django.contrib.auth import get_user_model  # type: ignore[import]

User = get_user_model()


def transliterate(text):
    """Проста транслітерація для генерації email."""
    mapping = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ye',
        'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k', 'л': 'l',
        'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'yu', 'я': 'ya'
    }
    res = ''.join(mapping.get(c.lower(), None) or c for c in text)
    return res.replace("'", "").replace(" ", "_")


def create_initial_data():
    print("🧹 Очищення бази даних...")
    # Спочатку видаляємо залежні записи
    models_to_clean = [
        StudentPerformance, Lesson, ScheduleTemplate, EvaluationType,
        TeachingAssignment, Subject, StudyGroup, AbsenceReason,
        Classroom, TimeSlot, GradeRule, GradingScale
    ]
    for model in models_to_clean:
        model.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    print("✅ База очищена.\n")

    # 1. Причини пропусків
    reasons_data = [
        ('Н', 'Неявка', False),
        ('Б', 'Хвороба', True),
        ('ПП', 'Поважна причина', True),
        ('В', 'Відпустка', True),
    ]
    reasons = [AbsenceReason.objects.create(code=c, description=d, is_respectful=r) for c, d, r in reasons_data]
    print(f"✅ Створено {len(reasons)} причини пропусків.")

    # 2. Шкала оцінювання (100-бальна)
    scale = GradingScale.objects.create(name="100-бальна шкала", is_default=True)
    grade_rules_data = [
        ("Відмінно (A)", 90, 100, "#22c55e"),
        ("Добре (B)",    75, 89,  "#84cc16"),
        ("Добре (C)",    65, 74,  "#eab308"),
        ("Задовільно (D)", 55, 64, "#f97316"),
        ("Задовільно (E)", 50, 54, "#ef4444"),
        ("Незадовільно (FX)", 0, 49, "#dc2626"),
    ]
    for label, mn, mx, color in grade_rules_data:
        GradeRule.objects.create(scale=scale, label=label, min_points=mn, max_points=mx, color=color)
    print("✅ Шкала оцінювання створена.")

    # 3. Групи (5 груп)
    group_data = [
        ("КН-41", 2022, 2026, "Комп'ютерні науки", 4),
        ("КН-42", 2022, 2026, "Комп'ютерні науки", 4),
        ("ІПЗ-11", 2023, 2027, "Інженерія програмного забезпечення", 3),
        ("ІПЗ-12", 2023, 2027, "Інженерія програмного забезпечення", 3),
        ("CS-21",  2021, 2025, "Комп'ютерні науки (англ.)", 5),
    ]
    groups = []
    for name, ye, gy, spec, course in group_data:
        groups.append(StudyGroup.objects.create(
            name=name, year_of_entry=ye, graduation_year=gy, specialty=spec, course=course
        ))
    print(f"✅ Створено {len(groups)} групи.")

    # 4. Аудиторії
    classrooms = []
    for r in [1, 2]:
        for i in range(1, 6):
            classrooms.append(Classroom.objects.create(
                name=f"{r}0{i}",
                capacity=30,
                building=f"Корпус {r}",
                floor=r,
                type=random.choice(['lecture', 'computer', 'lab'])
            ))
    print(f"✅ Створено {len(classrooms)} аудиторій.")

    # 5. Часові слоти (5 пар на день)
    time_data = [
        (1, time(8, 30),  time(10, 0)),
        (2, time(10, 0),  time(11, 30)),
        (3, time(11, 40), time(13, 10)),
        (4, time(13, 30), time(15, 0)),
        (5, time(15, 0),  time(16, 30)),
    ]
    time_slots = [TimeSlot.objects.create(lesson_number=n, start_time=s, end_time=e) for n, s, e in time_data]
    print(f"✅ Створено {len(time_slots)} часових слотів.")

    # 6. Предмети
    subject_names = [
        "Вища математика", "Об'єктно-орієнтоване програмування", "Бази даних",
        "Веб-технології", "Алгоритми та структури даних", "Комп'ютерні мережі",
        "Архітектура ЕОМ", "Фізика"
    ]
    subjects = [Subject.objects.create(name=name) for name in subject_names]
    print(f"✅ Створено {len(subjects)} предметів.")

    # 7. Викладачі (10 осіб)
    t_last_names = [
        "Мельник", "Шевченко", "Бойко", "Ткаченко", "Коваленко",
        "Бондар", "Олійник", "Вовк", "Поліщук", "Кравченко"
    ]
    teachers = []
    for ln in t_last_names:
        prefix = f"t_{transliterate(ln)}"
        user = User.objects.create_user(
            email=f"{prefix}@gmail.com",
            password=prefix,
            full_name=f"Проф. {ln}",
            role='teacher'
        )
        teachers.append(user)
    print(f"✅ Створено {len(teachers)} викладачів.")

    # 8. Студенти (40 осіб)
    s_last_names = [
        "Іваненко", "Петренко", "Сидоренко", "Кушнір", "Лисенко",
        "Руденко", "Мороз", "Харченко", "Василенко", "Павленко",
        "Савченко", "Козак", "Жук", "Кот", "Сорока",
        "Ворона", "Гончар", "Швець", "Кравець", "Ткач",
        "Коваль", "Гармаш", "Скляр", "Мельниченко", "Білоус",
        "Чорний", "Білий", "Сизий", "Мазур", "Дуб",
        "Береза", "Явір", "Гайдай", "Довженко", "Стус",
        "Костенко", "Тичина", "Рильський", "Сосюра", "Гончаренко"
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
    print(f"✅ Створено {len(students)} студентів.")

    # 9. Призначення та типи оцінювання
    assignments = []
    for group in groups:
        group_subjects = random.sample(subjects, 6)  # 6 предметів на групу
        for subj in group_subjects:
            teacher = random.choice(teachers)
            assign = TeachingAssignment.objects.create(teacher=teacher, subject=subj, group=group)
            assignments.append(assign)
            EvaluationType.objects.create(assignment=assign, name="Лекція",      weight_percent=20, order=1)
            EvaluationType.objects.create(assignment=assign, name="Практична",   weight_percent=50, order=2)
            EvaluationType.objects.create(assignment=assign, name="Лабораторна", weight_percent=30, order=3)
    print(f"✅ Створено {len(assignments)} призначень викладачів.")

    # 10. Шаблони розкладу (valid_from — auto_now_add, не передаємо!)
    templates = []
    for group in groups:
        group_assigns = [a for a in assignments if a.group == group]
        for day in range(1, 6):  # Пн–Пт
            daily_subjects = random.sample(group_assigns, min(4, len(group_assigns)))
            for i, assign in enumerate(daily_subjects):
                slot = time_slots[i]  # type: ignore
                tmpl = ScheduleTemplate(
                    teaching_assignment=assign,
                    group=group,
                    subject=assign.subject,
                    teacher=assign.teacher,
                    day_of_week=day,
                    lesson_number=slot.lesson_number,
                    start_time=slot.start_time,
                    duration_minutes=80,
                    classroom=random.choice(classrooms),
                )
                tmpl.save()
                templates.append(tmpl)
    print(f"✅ Створено {len(templates)} шаблонів розкладу.")

    # 11. Генерація уроків та оцінок за 2 місяці
    today = date.today()
    start_date = today - timedelta(days=60)
    current_date = start_date

    print(f"\n⏳ Генерація даних з {start_date} по {today}...")
    lesson_count: int = 0
    perf_count: int = 0

    while current_date <= today:
        weekday = current_date.weekday() + 1  # Python: 0=Пн → 1=Пн
        if weekday <= 5:
            day_templates = [t for t in templates if t.day_of_week == weekday]
            for tmpl in day_templates:
                eval_type = tmpl.teaching_assignment.evaluation_types.order_by('?').first()
                lesson = Lesson.objects.create(
                    group=tmpl.group,
                    subject=tmpl.subject,
                    teacher=tmpl.teacher,
                    date=current_date,
                    start_time=tmpl.start_time,
                    end_time=(datetime.combine(current_date, tmpl.start_time) + timedelta(minutes=80)).time(),
                    evaluation_type=eval_type,
                    max_points=100
                )
                lesson_count += 1  # type: ignore

                group_students = [s for s in students if s.group == tmpl.group]
                for student in group_students:
                    dice = random.random()
                    if dice < 0.1:  # 10% — пропуск
                        StudentPerformance.objects.create(lesson=lesson, student=student, absence=reasons[0])  # type: ignore
                    elif dice < 0.8:  # 70% — отримали оцінку
                        StudentPerformance.objects.create(
                            lesson=lesson, student=student,
                            earned_points=random.randint(55, 100),
                            comment="Автоматично згенеровано"
                        )
                    perf_count += 1  # type: ignore
        current_date += timedelta(days=1)

    print(f"\n✅ Успішно! Створено:")
    print(f"  - {len(groups)} груп та {len(subjects)} предметів")
    print(f"  - {len(teachers)} викладачів та {len(students)} студентів")
    print(f"  - {len(templates)} шаблонів, {lesson_count} уроків, {perf_count} записів успішності")
    print(f"\n🔑 ПРИКЛАД ВХОДУ:")
    print(f"  Викладач : {teachers[0].email}  /  Пароль: t_{transliterate(t_last_names[0])}")  # type: ignore
    print(f"  Студент  : {students[0].email}  /  Пароль: s_{transliterate(s_last_names[0])}_0")  # type: ignore


if __name__ == '__main__':
    create_initial_data()