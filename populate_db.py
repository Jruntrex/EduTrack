import os
import django
import random
from datetime import date, timedelta, datetime, time

# Setup Django Environment
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

def create_initial_data():
    print("🧹 Cleaning old database...")
    StudentPerformance.objects.all().delete()
    Lesson.objects.all().delete()
    ScheduleTemplate.objects.all().delete()
    EvaluationType.objects.all().delete()
    TeachingAssignment.objects.all().delete()
    Subject.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    StudyGroup.objects.all().delete()
    AbsenceReason.objects.all().delete()
    Classroom.objects.all().delete()
    TimeSlot.objects.all().delete()
    GradingScale.objects.all().delete()
    GradeRule.objects.all().delete()

    print("✅ Database cleaned.")

    # --- 1. Absence Reasons ---
    # --- 1. Absence Reasons ---
    reasons = [
        AbsenceReason.objects.create(code='Н', description='Неявка', is_respectful=False),
        AbsenceReason.objects.create(code='Хв', description='Хвороба', is_respectful=True),
        AbsenceReason.objects.create(code='ПП', description='Поважна причина', is_respectful=True),
    ]
    print("✅ Absence reasons created.")

    # --- 2. Groups ---
    group_names = ["КН-41", "КН-42", "ІПЗ-11", "ІПЗ-12", "CS-51"]
    groups = [StudyGroup.objects.create(name=name) for name in group_names]
    print(f"✅ Created {len(groups)} groups.")

    # --- 3. Classrooms ---
    classroom_names = [f"10{i}" for i in range(1, 6)] + [f"20{i}" for i in range(1, 6)] + ["Lab-1", "Lab-2", "Gym"]
    classrooms = [Classroom.objects.create(name=name, capacity=random.randint(20, 60)) for name in classroom_names]
    print(f"✅ Created {len(classrooms)} classrooms.")

    # --- 4. Time Slots ---
    # Standard pairs schedule
    time_slots_data = [
        (1, time(8, 30), time(9, 50)),
        (2, time(10, 00), time(11, 20)),
        (3, time(11, 40), time(13, 00)),
        (4, time(13, 30), time(14, 50)),
        (5, time(15, 00), time(16, 20)),
    ]
    time_slots = []
    for num, start, end in time_slots_data:
        time_slots.append(TimeSlot.objects.create(lesson_number=num, start_time=start, end_time=end))
    print(f"✅ Created {len(time_slots)} time slots.")

    # --- 5. Subjects (Sea of subjects) ---
    subject_names = [
        "Вища математика", "Об'єктно-орієнтоване програмування", "Філософія", 
        "Іноземна мова", "Фізика", "Бази даних", "Комп'ютерні мережі", 
        "Веб-розробка", "Алгоритми та структури даних", "Дискретна математика",
        "Операційні системи", "Архітектура комп'ютерів", "Кібербезпека",
        "Штучний інтелект", "Менеджмент проектів", "Соціологія", "Основи права",
        "Фізкультура", "Теорія ймовірностей", "Хмарні технології"
    ]
    subjects = [Subject.objects.create(name=name) for name in subject_names]
    print(f"✅ Created {len(subjects)} subjects.")

    # --- 6. Grading Scales ---
    scale_100 = GradingScale.objects.create(name="100-бальна")
    GradeRule.objects.create(scale=scale_100, label="A", min_points=90)
    GradeRule.objects.create(scale=scale_100, label="B", min_points=82)
    GradeRule.objects.create(scale=scale_100, label="C", min_points=74)
    GradeRule.objects.create(scale=scale_100, label="D", min_points=64)
    GradeRule.objects.create(scale=scale_100, label="E", min_points=60)
    GradeRule.objects.create(scale=scale_100, label="F", min_points=0)
    print("✅ Grading scales created.")

    # --- 7. Teachers (10) ---
    first_names = ["Олена", "Іван", "Петро", "Марія", "Андрій", "Світлана", "Дмитро", "Наталія", "Юрій", "Оксана"]
    last_names = ["Коваленко", "Шевченко", "Бойко", "Ткаченко", "Кравченко", "Олійник", "Вовк", "Бондар", "Мельник", "Поліщук"]
    
    teachers = []
    for i in range(10):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        # Ensure unique email
        email = f"teacher{i+1}@example.com"
        user = User.objects.create_user(
            email=email,
            password="password",
            full_name=name,
            role='teacher'
        )
        teachers.append(user)
    print(f"✅ Created {len(teachers)} teachers.")

    # --- 8. Students (40) ---
    students = []
    local_first_names = ["Олександр", "Максим", "Артем", "Дмитро", "Денис", "Андрій", "Богдан", "Дар'я", "Марія", "Софія", 
                        "Анна", "Вікторія", "Анастасія", "Микола", "Ігор", "Василь", "Павло", "Олег", "Едуард", "Роман"]
    
    for i in range(40):
        group = groups[i % len(groups)] # Distribute among groups
        name = f"{random.choice(local_first_names)} {random.choice(last_names)}"
        email = f"student{i+1}@example.com"
        user = User.objects.create_user(
            email=email,
            password="password",
            full_name=name,
            role='student',
            group=group
        )
        students.append(user)
    print(f"✅ Created {len(students)} students.")

    # --- 9. Teaching Assignments (The Core) ---
    # Assign each group ~8 subjects with random teachers
    assignments = []
    
    for group in groups:
        # Pick 8 random subjects for this group
        group_subjects = random.sample(subjects, 8)
        
        for subj in group_subjects:
            teacher = random.choice(teachers)
            
            # Check duplicates (teacher+subject+group must be unique)
            if not TeachingAssignment.objects.filter(teacher=teacher, subject=subj, group=group).exists():
                assign = TeachingAssignment.objects.create(teacher=teacher, subject=subj, group=group)
                assignments.append(assign)
                
                # Add Evaluation Types
                EvaluationType.objects.create(assignment=assign, name="Лекція", weight_percent=30)
                EvaluationType.objects.create(assignment=assign, name="Практична", weight_percent=40)
                EvaluationType.objects.create(assignment=assign, name="Лабораторна", weight_percent=30)

    print(f"✅ Created {len(assignments)} teaching assignments.")

    # --- 10. Schedule Templates ---
    # Generate a weekly schedule for each group
    templates = []
    
    for group in groups:
        # Filter assignments for this group
        group_assignments = [a for a in assignments if a.group == group]
        
        # 5 days a week
        for day in range(1, 6): # 1=Mon, 5=Fri
            # Randomly 3 to 5 lessons per day
            num_lessons = random.randint(3, 5)
            # Pick subjects for today (allow repetition)
            day_assignments = [random.choice(group_assignments) for _ in range(num_lessons)]
            
            for i, assign in enumerate(day_assignments):
                slot_idx = i # 0 to 4
                if slot_idx >= len(time_slots): break
                
                slot = time_slots[slot_idx]
                classroom = random.choice(classrooms)
                
                tmpl = ScheduleTemplate.objects.create(
                    teaching_assignment=assign,
                    group=group,
                    subject=assign.subject,  # Legacy field
                    teacher=assign.teacher,   # Legacy field
                    day_of_week=day,
                    lesson_number=slot.lesson_number,
                    start_time=slot.start_time,
                    duration_minutes=slot.duration_minutes(),
                    classroom=classroom,
                    valid_from="2026-01-01"
                )
                templates.append(tmpl)
                
    print(f"✅ Created {len(templates)} schedule templates.")

    # --- 11. Generate Lessons and Performance Data ---
    today = date.today()
    start_date = today - timedelta(days=45) # 1.5 months back
    end_date = today + timedelta(days=14)   # 2 weeks forward
    
    print(f"⏳ Generating lessons from {start_date} to {end_date}...")
    
    current_date = start_date
    lessons_created = 0
    grades_created = 0
    
    while current_date <= end_date:
        weekday = current_date.weekday() + 1
        day_templates = [t for t in templates if t.day_of_week == weekday]
        
        for tmpl in day_templates:
            # Create Lesson
            start_dt = datetime.combine(current_date, tmpl.start_time)
            end_dt = start_dt + timedelta(minutes=tmpl.duration_minutes)
            
            # Helper to pick random evaluation type from the assignment
            possible_types = list(tmpl.teaching_assignment.evaluation_types.all())
            eval_type = random.choice(possible_types) if possible_types else None
            
            lesson = Lesson.objects.create(
                group=tmpl.group,
                subject=tmpl.subject,
                teacher=tmpl.teacher,
                date=current_date,
                start_time=tmpl.start_time,
                end_time=end_dt.time(),
                template_source=tmpl,
                topic=f"Topic: {tmpl.subject.name} - Part {random.randint(1, 20)}",
                classroom=tmpl.classroom,
                evaluation_type=eval_type,
                max_points=100
            )
            lessons_created += 1
            
            # If lesson is in the past, add grades/attendance
            if current_date <= today:
                group_students = [s for s in students if s.group == tmpl.group]
                
                for student in group_students:
                    dice = random.random()
                    
                    # 10% chance of absence
                    if dice < 0.10:
                        reason = random.choice(reasons) if random.random() < 0.3 else reasons[0] # Mostly 'Н' (unknown)
                        StudentPerformance.objects.create(
                            lesson=lesson,
                            student=student,
                            absence=reason
                        )
                    # 60% chance of getting a grade (if not absent)
                    elif dice < 0.70:
                        # Random grade skewed towards good marks
                        score = random.choices(
                            [60, 70, 80, 90, 95, 100], 
                            weights=[5, 15, 30, 30, 15, 5]
                        )[0]
                        StudentPerformance.objects.create(
                            lesson=lesson,
                            student=student,
                            earned_points=score,
                            comment="Good job" if score >= 90 else ""
                        )
                    grades_created += 1

        current_date += timedelta(days=1)

    print(f"✅ Generated {lessons_created} lessons and tons of grades.")
    print("\n--- TEST CREDENTIALS ---")
    print("Admin:   Use 'python manage.py createsuperuser' usually, but data is wiped.")
    print("Teacher: teacher1@example.com / password")
    print("Student: student1@example.com / password")

if __name__ == '__main__':
    create_initial_data()