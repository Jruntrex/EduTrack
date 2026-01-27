"""
Скрипт для заповнення бази даних тестовими даними через Django ORM
Використання: python populate_db.py
"""

import os
import sys
import django
from datetime import date, timedelta

# Налаштування Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edutrack_project.settings')
django.setup()

from main.models import (
    StudyGroup, User, Subject, TeachingAssignment, 
    EvaluationType, WeeklySchedule, LessonSession, 
    AbsenceReason, StudentPerformance
)

def clear_database():
    """Очищення всіх таблиць"""
    print("🗑️  Очищення бази даних...")
    StudentPerformance.objects.all().delete()
    LessonSession.objects.all().delete()
    WeeklySchedule.objects.all().delete()
    EvaluationType.objects.all().delete()
    TeachingAssignment.objects.all().delete()
    AbsenceReason.objects.all().delete()
    Subject.objects.all().delete()
    User.objects.all().delete()
    StudyGroup.objects.all().delete()
    print("✅ База даних очищена")

def create_groups():
    """Створення груп студентів"""
    print("\n📚 Створення груп...")
    groups = [
        StudyGroup(name='КН-41'),
        StudyGroup(name='КН-42'),
        StudyGroup(name='ІП-31'),
        StudyGroup(name='ІП-32'),
    ]
    StudyGroup.objects.bulk_create(groups)
    print(f"✅ Створено {len(groups)} груп")
    return {g.name: g for g in StudyGroup.objects.all()}

def create_users(groups):
    """Створення користувачів"""
    print("\n👥 Створення користувачів...")
    
    # Адміністратор
    admin = User(
        full_name='Іванов Іван Іванович',
        email='admin@edutrack.com',
        role='admin'
    )
    admin.set_password('password123')
    admin.save()
    
    # Викладачі
    teachers = []
    teacher_data = [
        ('Петренко Петро Петрович', 'petrenko@edutrack.com'),
        ('Сидоренко Ольга Миколаївна', 'sydorenko@edutrack.com'),
        ('Коваленко Марія Володимирівна', 'kovalenko@edutrack.com'),
        ('Шевченко Андрій Сергійович', 'shevchenko@edutrack.com'),
    ]
    
    for name, email in teacher_data:
        teacher = User(full_name=name, email=email, role='teacher')
        teacher.set_password('password123')
        teacher.save()
        teachers.append(teacher)
    
    # Студенти КН-41
    students_kn41 = [
        ('Бондаренко Олександр Іванович', 'bondarenko.o@student.com'),
        ('Мельник Анна Петрівна', 'melnyk.a@student.com'),
        ('Ткаченко Дмитро Олегович', 'tkachenko.d@student.com'),
        ('Лисенко Катерина Вікторівна', 'lysenko.k@student.com'),
        ('Гриценко Максим Андрійович', 'hrytsenko.m@student.com'),
    ]
    
    for name, email in students_kn41:
        student = User(full_name=name, email=email, role='student', group=groups['КН-41'])
        student.set_password('password123')
        student.save()
    
    # Студенти КН-42
    students_kn42 = [
        ('Павленко Юлія Сергіївна', 'pavlenko.y@student.com'),
        ('Романенко Віктор Миколайович', 'romanenko.v@student.com'),
        ('Кравченко Ірина Олександрівна', 'kravchenko.i@student.com'),
    ]
    
    for name, email in students_kn42:
        student = User(full_name=name, email=email, role='student', group=groups['КН-42'])
        student.set_password('password123')
        student.save()
    
    # Студенти ІП-31
    students_ip31 = [
        ('Морозов Олег Васильович', 'morozov.o@student.com'),
        ('Захарова Софія Дмитрівна', 'zakharova.s@student.com'),
    ]
    
    for name, email in students_ip31:
        student = User(full_name=name, email=email, role='student', group=groups['ІП-31'])
        student.set_password('password123')
        student.save()
    
    print(f"✅ Створено {User.objects.count()} користувачів")
    return {
        'admin': admin,
        'teachers': teachers,
        'students_kn41': User.objects.filter(role='student', group=groups['КН-41']),
        'students_kn42': User.objects.filter(role='student', group=groups['КН-42']),
    }

def create_subjects():
    """Створення предметів"""
    print("\n📖 Створення предметів...")
    subjects_data = [
        ('Вища математика', 'Курс вищої математики для студентів технічних спеціальностей'),
        ('Програмування', 'Основи програмування на Python та Java'),
        ('Бази даних', 'Проектування та робота з реляційними базами даних'),
        ('Веб-технології', 'Розробка веб-додатків з використанням HTML, CSS, JavaScript'),
        ('Алгоритми та структури даних', 'Вивчення основних алгоритмів та структур даних'),
        ('Операційні системи', 'Принципи роботи операційних систем'),
    ]
    
    subjects = []
    for name, desc in subjects_data:
        subjects.append(Subject(name=name, description=desc))
    
    Subject.objects.bulk_create(subjects)
    print(f"✅ Створено {len(subjects)} предметів")
    return {s.name: s for s in Subject.objects.all()}

def create_teaching_assignments(subjects, users, groups):
    """Створення призначень викладачів"""
    print("\n👨‍🏫 Створення призначень викладачів...")
    teachers = users['teachers']
    
    assignments = [
        # Петренко - Математика
        TeachingAssignment(subject=subjects['Вища математика'], teacher=teachers[0], group=groups['КН-41']),
        TeachingAssignment(subject=subjects['Вища математика'], teacher=teachers[0], group=groups['КН-42']),
        
        # Сидоренко - Програмування
        TeachingAssignment(subject=subjects['Програмування'], teacher=teachers[1], group=groups['КН-41']),
        TeachingAssignment(subject=subjects['Програмування'], teacher=teachers[1], group=groups['ІП-31']),
        
        # Коваленко - Бази даних та Алгоритми
        TeachingAssignment(subject=subjects['Бази даних'], teacher=teachers[2], group=groups['КН-41']),
        TeachingAssignment(subject=subjects['Алгоритми та структури даних'], teacher=teachers[2], group=groups['ІП-31']),
        
        # Шевченко - Веб-технології
        TeachingAssignment(subject=subjects['Веб-технології'], teacher=teachers[3], group=groups['КН-42']),
    ]
    
    TeachingAssignment.objects.bulk_create(assignments)
    print(f"✅ Створено {len(assignments)} призначень")
    return list(TeachingAssignment.objects.all())

def create_evaluation_types(assignments):
    """Створення типів оцінювання"""
    print("\n📊 Створення типів оцінювання...")
    
    eval_types = []
    
    # Для кожного призначення створюємо типи оцінювання
    for assignment in assignments:
        if 'Математика' in assignment.subject.name:
            eval_types.extend([
                EvaluationType(assignment=assignment, name='Лекція', weight_percent=10),
                EvaluationType(assignment=assignment, name='Практика', weight_percent=20),
                EvaluationType(assignment=assignment, name='Лабораторна робота', weight_percent=30),
                EvaluationType(assignment=assignment, name='Екзамен', weight_percent=40),
            ])
        elif 'Програмування' in assignment.subject.name:
            eval_types.extend([
                EvaluationType(assignment=assignment, name='Лекція', weight_percent=15),
                EvaluationType(assignment=assignment, name='Лабораторна робота', weight_percent=45),
                EvaluationType(assignment=assignment, name='Проект', weight_percent=40),
            ])
        elif 'Бази даних' in assignment.subject.name:
            eval_types.extend([
                EvaluationType(assignment=assignment, name='Лекція', weight_percent=10),
                EvaluationType(assignment=assignment, name='Практика', weight_percent=25),
                EvaluationType(assignment=assignment, name='Курсова робота', weight_percent=35),
                EvaluationType(assignment=assignment, name='Екзамен', weight_percent=30),
            ])
        else:
            eval_types.extend([
                EvaluationType(assignment=assignment, name='Лекція', weight_percent=10),
                EvaluationType(assignment=assignment, name='Практика', weight_percent=30),
                EvaluationType(assignment=assignment, name='Проект', weight_percent=60),
            ])
    
    EvaluationType.objects.bulk_create(eval_types)
    print(f"✅ Створено {len(eval_types)} типів оцінювання")

def create_schedule(assignments):
    """Створення розкладу"""
    print("\n📅 Створення розкладу...")
    
    schedule = []
    
    # КН-41
    kn41_math = assignments[0]
    kn41_prog = assignments[2]
    kn41_db = assignments[4]
    
    schedule.extend([
        # Понеділок
        WeeklySchedule(assignment=kn41_math, day_of_week=1, lesson_number=1),
        WeeklySchedule(assignment=kn41_prog, day_of_week=1, lesson_number=2),
        # Вівторок
        WeeklySchedule(assignment=kn41_db, day_of_week=2, lesson_number=1),
        WeeklySchedule(assignment=kn41_math, day_of_week=2, lesson_number=3),
        # Середа
        WeeklySchedule(assignment=kn41_prog, day_of_week=3, lesson_number=2),
    ])
    
    # КН-42
    kn42_math = assignments[1]
    kn42_web = assignments[6]
    
    schedule.extend([
        # Понеділок
        WeeklySchedule(assignment=kn42_math, day_of_week=1, lesson_number=2),
        WeeklySchedule(assignment=kn42_web, day_of_week=1, lesson_number=3),
        # Четвер
        WeeklySchedule(assignment=kn42_math, day_of_week=4, lesson_number=1),
    ])
    
    WeeklySchedule.objects.bulk_create(schedule)
    print(f"✅ Створено {len(schedule)} записів розкладу")

def create_absence_reasons():
    """Створення причин пропусків"""
    print("\n❌ Створення причин пропусків...")
    
    reasons = [
        AbsenceReason(code='Н', description='Неповажна причина', is_respectful=False),
        AbsenceReason(code='Б', description='Хвороба (з довідкою)', is_respectful=True),
        AbsenceReason(code='В', description='Відрядження', is_respectful=True),
        AbsenceReason(code='П', description='Поважна причина', is_respectful=True),
    ]
    
    AbsenceReason.objects.bulk_create(reasons)
    print(f"✅ Створено {len(reasons)} причин пропусків")
    return {r.code: r for r in AbsenceReason.objects.all()}

def create_lessons_and_performance(assignments, users, absence_reasons):
    """Створення занять та успішності студентів"""
    print("\n📝 Створення занять та оцінок...")
    
    # Отримуємо призначення для КН-41
    kn41_math = assignments[0]
    kn41_prog = assignments[2]
    kn41_db = assignments[4]
    
    # Отримуємо типи оцінювання
    math_lecture = EvaluationType.objects.get(assignment=kn41_math, name='Лекція')
    math_practice = EvaluationType.objects.get(assignment=kn41_math, name='Практика')
    prog_lecture = EvaluationType.objects.get(assignment=kn41_prog, name='Лекція')
    prog_lab = EvaluationType.objects.get(assignment=kn41_prog, name='Лабораторна робота')
    db_lecture = EvaluationType.objects.get(assignment=kn41_db, name='Лекція')
    db_practice = EvaluationType.objects.get(assignment=kn41_db, name='Практика')
    
    # Студенти КН-41
    students = list(users['students_kn41'])
    
    # Створюємо заняття за останні 2 тижні
    base_date = date(2026, 1, 13)  # Понеділок
    
    lessons = []
    performances = []
    
    # Тиждень 1
    # Понеділок 13.01
    lesson1 = LessonSession.objects.create(
        assignment=kn41_math, date=base_date, lesson_number=1,
        evaluation_type=math_lecture, topic='Вступ до диференціального числення'
    )
    lesson2 = LessonSession.objects.create(
        assignment=kn41_prog, date=base_date, lesson_number=2,
        evaluation_type=prog_lecture, topic='Основи Python: змінні та типи даних'
    )
    
    # Оцінки для lesson1
    grades1 = [85, 90, 75, None, 80]
    for i, student in enumerate(students):
        perf = StudentPerformance(
            lesson=lesson1, student=student,
            grade=grades1[i],
            absence=absence_reasons['Н'] if grades1[i] is None else None,
            comment='Активна участь' if i == 0 else ('Відмінна робота' if i == 1 else '')
        )
        performances.append(perf)
    
    # Оцінки для lesson2
    grades2 = [88, 92, 78, None, 85]
    for i, student in enumerate(students):
        perf = StudentPerformance(
            lesson=lesson2, student=student,
            grade=grades2[i],
            absence=absence_reasons['Н'] if grades2[i] is None else None,
            comment='Чудові запитання' if i == 1 else ''
        )
        performances.append(perf)
    
    # Вівторок 14.01
    lesson3 = LessonSession.objects.create(
        assignment=kn41_db, date=base_date + timedelta(days=1), lesson_number=1,
        evaluation_type=db_lecture, topic='Вступ до реляційних баз даних'
    )
    lesson4 = LessonSession.objects.create(
        assignment=kn41_math, date=base_date + timedelta(days=1), lesson_number=3,
        evaluation_type=math_practice, topic='Похідна функції'
    )
    
    # Оцінки для lesson3
    grades3 = [82, 95, 70, 75, 88]
    comments3 = ['', 'Відмінне розуміння теми', 'Потребує додаткової роботи', 'Був присутній', '']
    for i, student in enumerate(students):
        perf = StudentPerformance(
            lesson=lesson3, student=student,
            grade=grades3[i], comment=comments3[i]
        )
        performances.append(perf)
    
    # Оцінки для lesson4
    grades4 = [90, 95, 80, 65, 85]
    comments4 = ['Всі завдання виконані', '', '', 'Не всі завдання', '']
    for i, student in enumerate(students):
        perf = StudentPerformance(
            lesson=lesson4, student=student,
            grade=grades4[i], comment=comments4[i]
        )
        performances.append(perf)
    
    # Середа 15.01
    lesson5 = LessonSession.objects.create(
        assignment=kn41_prog, date=base_date + timedelta(days=2), lesson_number=2,
        evaluation_type=prog_lab, topic='Лабораторна: Робота зі списками'
    )
    
    # Оцінки для lesson5
    grades5 = [95, 100, 85, 70, 90]
    comments5 = ['Відмінна лабораторна', 'Перфектне виконання', '', 'Є помилки', '']
    for i, student in enumerate(students):
        perf = StudentPerformance(
            lesson=lesson5, student=student,
            grade=grades5[i], comment=comments5[i]
        )
        performances.append(perf)
    
    # Тиждень 2 (20-22 січня)
    week2_date = base_date + timedelta(days=7)
    
    # Понеділок 20.01
    lesson6 = LessonSession.objects.create(
        assignment=kn41_math, date=week2_date, lesson_number=1,
        evaluation_type=math_lecture, topic='Інтеграли та їх застосування'
    )
    lesson7 = LessonSession.objects.create(
        assignment=kn41_prog, date=week2_date, lesson_number=2,
        evaluation_type=prog_lecture, topic='Функції в Python'
    )
    
    # Оцінки для тижня 2
    grades6 = [87, 93, 76, 80, 82]
    grades7 = [90, 94, 80, None, 86]
    
    for i, student in enumerate(students):
        performances.append(StudentPerformance(lesson=lesson6, student=student, grade=grades6[i]))
        performances.append(StudentPerformance(
            lesson=lesson7, student=student, grade=grades7[i],
            absence=absence_reasons['Б'] if grades7[i] is None else None,
            comment='Хворів' if grades7[i] is None else ''
        ))
    
    # Масове створення успішності
    StudentPerformance.objects.bulk_create(performances)
    
    print(f"✅ Створено {LessonSession.objects.count()} занять")
    print(f"✅ Створено {StudentPerformance.objects.count()} записів успішності")

def main():
    """Головна функція"""
    print("=" * 60)
    print("🚀 ЗАПОВНЕННЯ БАЗИ ДАНИХ ТЕСТОВИМИ ДАНИМИ")
    print("=" * 60)
    
    try:
        clear_database()
        groups = create_groups()
        users = create_users(groups)
        subjects = create_subjects()
        assignments = create_teaching_assignments(subjects, users, groups)
        create_evaluation_types(assignments)
        create_schedule(assignments)
        absence_reasons = create_absence_reasons()
        create_lessons_and_performance(assignments, users, absence_reasons)
        
        print("\n" + "=" * 60)
        print("✅ БАЗА ДАНИХ УСПІШНО ЗАПОВНЕНА!")
        print("=" * 60)
        print("\n📊 Статистика:")
        print(f"   • Груп: {StudyGroup.objects.count()}")
        print(f"   • Користувачів: {User.objects.count()}")
        print(f"   • Предметів: {Subject.objects.count()}")
        print(f"   • Призначень: {TeachingAssignment.objects.count()}")
        print(f"   • Типів оцінювання: {EvaluationType.objects.count()}")
        print(f"   • Записів розкладу: {WeeklySchedule.objects.count()}")
        print(f"   • Проведених занять: {LessonSession.objects.count()}")
        print(f"   • Причин пропусків: {AbsenceReason.objects.count()}")
        print(f"   • Записів успішності: {StudentPerformance.objects.count()}")
        print("\n🔑 Дані для входу:")
        print("   Адміністратор: admin@edutrack.com / password123")
        print("   Викладач: petrenko@edutrack.com / password123")
        print("   Студент: bondarenko.o@student.com / password123")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ПОМИЛКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
