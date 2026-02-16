"""
Schedule Service - Business Logic для системи розкладу

Цей модуль містить функції для:
- Валідації розкладу
- Перевірки конфліктів (час, викладач, аудиторія)
- Управління шаблонами розкладу
"""

from datetime import date, time, datetime, timedelta
from typing import Optional, Tuple

from django.db.models import Q
from main.models import (
    ScheduleTemplate,
    StudyGroup,
    User,
    Classroom,
    Subject,
)


def check_time_overlap(
    start1: time,
    duration1: int,
    start2: time,
    duration2: int
) -> bool:
    """
    Перевірка перетину двох часових інтервалів.
    
    Args:
        start1: Час початку першого інтервалу
        duration1: Тривалість першого інтервалу в хвилинах
        start2: Час початку другого інтервалу
        duration2: Тривалість другого інтервалу в хвилинах
    
    Returns:
        True якщо інтервали перетинаються, False якщо ні
    
    Example:
        >>> check_time_overlap(time(8, 30), 80, time(9, 0), 80)
        True  # 08:30-09:50 перетинається з 09:00-10:20
        >>> check_time_overlap(time(8, 30), 80, time(10, 0), 80)
        False  # 08:30-09:50 не перетинається з 10:00-11:20
    """
    # Конвертуємо часи в datetime для розрахунків
    base_date = date.today()
    start1_dt = datetime.combine(base_date, start1)
    end1_dt = start1_dt + timedelta(minutes=duration1)
    
    start2_dt = datetime.combine(base_date, start2)
    end2_dt = start2_dt + timedelta(minutes=duration2)
    
    # Перетин інтервалів: max(start) < min(end)
    return max(start1_dt, start2_dt) < min(end1_dt, end2_dt)


def validate_schedule_slot(
    group: StudyGroup,
    day: int,
    lesson_number: int,
    start_time: time,
    duration: int,
    subject: Subject,
    teacher: Optional[User] = None,
    classroom: Optional[Classroom] = None,
    exclude_slot_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Валідація слоту розкладу на наявність конфліктів.
    
    Перевіряє:
    1. Чи не перетинається з іншими парами тієї ж групи
    2. Чи не зайнятий викладач в цей час
    3. Чи не зайнята аудиторія в цей час
    
    Args:
        group: Група
        day: День тижня (1-7)
        lesson_number: Номер пари
        start_time: Час початку
        duration: Тривалість в хвилинах
        subject: Предмет
        teacher: Викладач (опціонально)
        classroom: Аудиторія (опціонально)
        exclude_slot_id: ID слоту, який не враховувати (для редагування)
    
    Returns:
        Tuple (is_valid, error_message)
        - is_valid: True якщо валідний, False якщо є конфлікт
        - error_message: Опис помилки або пустий рядок
    
    Example:
        >>> is_valid, error = validate_schedule_slot(
        ...     group=group_kn41,
        ...     day=1,
        ...     lesson_number=1,
        ...     start_time=time(8, 30),
        ...     duration=80,
        ...     teacher=teacher_ivanov
        ... )
        >>> if not is_valid:
        ...     print(error)
    """
    # 1. Перевірка конфліктів з іншими парами тієї ж групи
    group_conflicts = ScheduleTemplate.objects.filter(
        group=group,
        day_of_week=day
    )
    
    if exclude_slot_id:
        group_conflicts = group_conflicts.exclude(id=exclude_slot_id)
        print(f"🔍 DEBUG: Виключаємо слот ID={exclude_slot_id} з перевірки для групи {group.name}, день {day}")
    
    for conflict in group_conflicts:
        print(f"🔍 DEBUG: Перевіряємо конфлікт: ID={conflict.id}, пара №{conflict.lesson_number}, {conflict.subject.name}, {conflict.start_time}-{conflict.duration_minutes}хв")
        if check_time_overlap(
            start_time, duration,
            conflict.start_time, conflict.duration_minutes
        ):
            print(f"❌ DEBUG: КОНФЛІКТ! Час перетинається!")
            return (
                False,
                f"Конфлікт: Пара №{conflict.lesson_number} "
                f"({conflict.start_time.strftime('%H:%M')}) перетинається з цим часом"
            )
    
    # 2. Перевірка зайнятості викладача
    if teacher:
        teacher_conflicts = ScheduleTemplate.objects.filter(
            teacher=teacher,
            day_of_week=day
        )
        
        if exclude_slot_id:
            teacher_conflicts = teacher_conflicts.exclude(id=exclude_slot_id)
        
        for conflict in teacher_conflicts:
            if check_time_overlap(
                start_time, duration,
                conflict.start_time, conflict.duration_minutes
            ):
                # Перевірка на "Спільну пару" (Shared Lesson / Joint Class)
                # Допускаємо перетин, якщо це той самий викладач, предмет, та час початку.
                # Аудиторія може бути різною (наприклад, онлайн лекція для кількох груп)
                is_shared_lesson = (
                    conflict.subject_id == subject.id and
                    conflict.start_time == start_time
                )
                if is_shared_lesson:
                    continue
                
                return (
                    False,
                    f"Викладач {teacher.full_name} уже зайнятий у групі {conflict.group.name} "
                    f"на предметі '{conflict.subject.name}' о {conflict.start_time.strftime('%H:%M')} (ID: {conflict.id})"
                )
    
    # 3. Перевірка зайнятості аудиторії
    if classroom:
        classroom_conflicts = ScheduleTemplate.objects.filter(
            classroom=classroom,
            day_of_week=day
        )
        
        if exclude_slot_id:
            classroom_conflicts = classroom_conflicts.exclude(id=exclude_slot_id)
        
        for conflict in classroom_conflicts:
            if check_time_overlap(
                start_time, duration,
                conflict.start_time, conflict.duration_minutes
            ):
                # Також перевіряємо на спільну пару
                is_shared_lesson = (
                    conflict.teacher_id == (teacher.id if teacher else None) and
                    conflict.subject_id == subject.id and
                    conflict.start_time == start_time
                )
                if is_shared_lesson:
                    continue
                
                return (
                    False,
                    f"Аудиторія {classroom.name} зайнята групою {conflict.group.name} "
                    f"на предметі '{conflict.subject.name}' о {conflict.start_time.strftime('%H:%M')} (ID: {conflict.id})"
                )
    
    # Всі перевірки пройдені
    return (True, "")


def get_schedule_conflicts(
    schedule_template: ScheduleTemplate
) -> list[dict]:
    """
    Отримання всіх конфліктів для конкретного слоту розкладу.
    
    Args:
        schedule_template: Шаблон розкладу для перевірки
    
    Returns:
        Список конфліктів у форматі:
        [
            {
                'type': 'group' | 'teacher' | 'classroom',
                'message': 'опис конфлікту',
                'conflicting_slot': ScheduleTemplate object
            },
            ...
        ]
    """
    conflicts = []
    
    # Конфлікти по групі
    group_conflicts = ScheduleTemplate.objects.filter(
        group=schedule_template.group,
        day_of_week=schedule_template.day_of_week
    ).exclude(id=schedule_template.id)
    
    for conflict in group_conflicts:
        if check_time_overlap(
            schedule_template.start_time,
            schedule_template.duration_minutes,
            conflict.start_time,
            conflict.duration_minutes
        ):
            conflicts.append({
                'type': 'group',
                'message': f"Конфлікт з іншою парою (№{conflict.lesson_number})",
                'conflicting_slot': conflict,
            })
    
    # Конфлікти по викладачу
    if schedule_template.teacher:
        teacher_conflicts = ScheduleTemplate.objects.filter(
            teacher=schedule_template.teacher,
            day_of_week=schedule_template.day_of_week
        ).exclude(id=schedule_template.id)
        
        for conflict in teacher_conflicts:
            if check_time_overlap(
                schedule_template.start_time,
                schedule_template.duration_minutes,
                conflict.start_time,
                conflict.duration_minutes
            ):
                conflicts.append({
                    'type': 'teacher',
                    'message': f"Викладач зайнятий у групі {conflict.group.name}",
                    'conflicting_slot': conflict,
                })
    
    # Конфлікти по аудиторії
    if schedule_template.classroom:
        classroom_conflicts = ScheduleTemplate.objects.filter(
            classroom=schedule_template.classroom,
            day_of_week=schedule_template.day_of_week
        ).exclude(id=schedule_template.id)
        
        for conflict in classroom_conflicts:
            if check_time_overlap(
                schedule_template.start_time,
                schedule_template.duration_minutes,
                conflict.start_time,
                conflict.duration_minutes
            ):
                conflicts.append({
                    'type': 'classroom',
                    'message': f"Аудиторія зайнята групою {conflict.group.name}",
                    'conflicting_slot': conflict,
                })
    
    return conflicts


def get_available_teachers(
    day: int,
    start_time: time,
    duration: int,
    subject: Optional[Subject] = None
) -> list[User]:
    """
    Отримання списку викладачів, доступних в конкретний час.
    
    Args:
        day: День тижня (1-7)
        start_time: Час початку
        duration: Тривалість в хвилинах
        subject: Предмет (фільтрувати тільки викладачів цього предмету)
    
    Returns:
        Список викладачів (User objects)
    """
    # Всі викладачі
    teachers = User.objects.filter(role='teacher')
    
    if subject:
        # Фільтруємо тих, хто читає цей предмет
        teachers = teachers.filter(
            teachingassignment__subject=subject
        ).distinct()
    
    # Виключаємо зайнятих викладачів
    busy_teachers = ScheduleTemplate.objects.filter(
        day_of_week=day
    ).select_related('teacher')
    
    available_teachers = []
    for teacher in teachers:
        is_busy = False
        for slot in busy_teachers.filter(teacher=teacher):
            if check_time_overlap(
                start_time, duration,
                slot.start_time, slot.duration_minutes
            ):
                is_busy = True
                break
        
        if not is_busy:
            available_teachers.append(teacher)
    
    return available_teachers


def get_available_classrooms(
    day: int,
    start_time: time,
    duration: int,
    min_capacity: Optional[int] = None
) -> list[Classroom]:
    """
    Отримання списку вільних аудиторій в конкретний час.
    
    Args:
        day: День тижня (1-7)
        start_time: Час початку
        duration: Тривалість в хвилинах
        min_capacity: Мінімальна місткість (опціонально)
    
    Returns:
        Список аудиторій (Classroom objects)
    """
    classrooms = Classroom.objects.all()
    
    if min_capacity:
        classrooms = classrooms.filter(capacity__gte=min_capacity)
    
    # Виключаємо зайняті аудиторії
    busy_classrooms = ScheduleTemplate.objects.filter(
        day_of_week=day,
        classroom__isnull=False
    ).select_related('classroom')
    
    available_classrooms = []
    for classroom in classrooms:
        is_busy = False
        for slot in busy_classrooms.filter(classroom=classroom):
            if check_time_overlap(
                start_time, duration,
                slot.start_time, slot.duration_minutes
            ):
                is_busy = True
                break
        
        if not is_busy:
            available_classrooms.append(classroom)
    
    return available_classrooms


def find_all_schedule_conflicts() -> list[tuple[ScheduleTemplate, ScheduleTemplate]]:
    """
    Системна перевірка всіх шаблонів розкладу на наявність перетинів для викладачів.
    Використовується для діагностики здоров'я бази даних.
    """
    all_templates = ScheduleTemplate.objects.all().select_related('teacher', 'group', 'subject')
    
    # Групуємо по викладачу та дню
    by_teacher_day = {}
    for t in all_templates:
        if not t.teacher:
            continue
        key = (t.teacher.id, t.day_of_week)
        if key not in by_teacher_day:
            by_teacher_day[key] = []
        by_teacher_day[key].append(t)
    
    conflicts = []
    for key, templates in by_teacher_day.items():
        for i in range(len(templates)):
            for j in range(i + 1, len(templates)):
                t1 = templates[i]
                t2 = templates[j]
                if check_time_overlap(
                    t1.start_time, t1.duration_minutes,
                    t2.start_time, t2.duration_minutes
                ):
                    conflicts.append((t1, t2))
    
    return conflicts
