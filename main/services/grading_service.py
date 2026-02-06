"""
Grading Service - Business Logic для системи оцінювання

Цей модуль містить функції для:
- Розрахунку оцінок студентів
- Агрегації балів
- Конвертації балів у оцінки за шкалою
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from django.db.models import Avg, Count, Sum, Q, QuerySet
from main.models import User, Subject, StudentPerformance, GradingScale, GradeRule, Lesson, EvaluationType


def calculate_student_grade(
    student: User,
    subject: Subject,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> dict:
    """
    Розрахунок оцінки студента по предмету за період.
    
    Args:
        student: Об'єкт студента
        subject: Об'єкт предмету
        date_from: Початкова дата (опціонально)
        date_to: Кінцева дата (опціонально)
    
    Returns:
        dict з ключами:
            - total_points: загальна кількість балів
            - avg_points: середній бал
            - lessons_count: кількість занять
            - grades: список всіх оцінок
    """
    # Базовий запит
    performance = StudentPerformance.objects.filter(
        student=student,
        lesson__subject=subject,
        earned_points__isnull=False
    ).select_related('lesson')
    
    # Фільтрація по датам
    if date_from:
        performance = performance.filter(lesson__date__gte=date_from)
    if date_to:
        performance = performance.filter(lesson__date__lte=date_to)
    
    # Агрегація
    stats = performance.aggregate(
        total=Sum('earned_points'),
        average=Avg('earned_points'),
        count=Count('id')
    )
    
    # Список оцінок для детального аналізу
    grades_list = list(
        performance.values_list('earned_points', flat=True)
    )
    
    return {
        'total_points': float(stats['total'] or 0),
        'avg_points': float(stats['average'] or 0),
        'lessons_count': stats['count'],
        'grades': grades_list,
    }


def get_bayesian_average(
    grades: list[float],
    prior_mean: float = 3.0,
    prior_weight: int = 5
) -> float:
    """
    Розрахунок Bayesian Average (згладжений середній бал).
    
    Використовується для уникнення викривлення при малій кількості оцінок.
    Наприклад, якщо студент має одну "5", його середній не буде 5.0,
    а буде ближче до prior_mean.
    
    Args:
        grades: Список оцінок
        prior_mean: Апріорне середнє (за замовчуванням 3.0)
        prior_weight: Вага апріорного середнього
    
    Returns:
        Згладжений середній бал
    
    Example:
        >>> get_bayesian_average([5.0], prior_mean=3.0, prior_weight=5)
        3.33  # Замість 5.0
        >>> get_bayesian_average([5.0, 5.0, 5.0, 5.0, 5.0], prior_mean=3.0)
        4.5   # Більше ваги реальним оцінкам
    """
    if not grades:
        return prior_mean
    
    actual_sum = sum(grades)
    actual_count = len(grades)
    
    weighted_sum = actual_sum + (prior_mean * prior_weight)
    total_count = actual_count + prior_weight
    
    return weighted_sum / total_count


def convert_points_to_grade(
    points: float,
    scale: GradingScale
) -> str:
    """
    Конвертація балів у текстову оцінку за шкалою.
    
    Args:
        points: Кількість балів
        scale: Об'єкт шкали оцінювання
    
    Returns:
        Текстова оцінка (напр. "Відмінно", "A", тощо)
    
    Example:
        >>> scale = GradingScale.objects.get(name="100-бальна")
        >>> convert_points_to_grade(95, scale)
        "Відмінно"
        >>> convert_points_to_grade(75, scale)
        "Добре"
    """
    # Отримуємо всі правила для шкали (вже відсортовані по min_points DESC)
    rules = scale.rules.all()
    
    for rule in rules:
        if points >= float(rule.min_points):
            return rule.label
    
    # Якщо не знайдено відповідного правила
    return "Незараховано"


def get_student_absences_stats(
    student: User,
    subject: Optional[Subject] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> dict:
    """
    Статистика пропусків студента.
    
    Args:
        student: Об'єкт студента
        subject: Предмет (опціонально, для фільтрації)
        date_from: Початкова дата (опціонально)
        date_to: Кінцева дата (опціонально)
    
    Returns:
        dict з ключами:
            - total_absences: загальна кількість пропусків
            - respectful: кількість поважних пропусків
            - unrespectful: кількість неповажних пропусків
            - by_reason: розбивка по причинах {код: кількість}
    """
    absences = StudentPerformance.objects.filter(
        student=student,
        absence__isnull=False
    ).select_related('absence', 'lesson')
    
    if subject:
        absences = absences.filter(lesson__subject=subject)
    if date_from:
        absences = absences.filter(lesson__date__gte=date_from)
    if date_to:
        absences = absences.filter(lesson__date__lte=date_to)
    
    total = absences.count()
    respectful = absences.filter(absence__is_respectful=True).count()
    unrespectful = absences.filter(absence__is_respectful=False).count()
    
    # Розбивка по причинах
    by_reason = {}
    for perf in absences.select_related('absence'):
        code = perf.absence.code
        by_reason[code] = by_reason.get(code, 0) + 1
    
    return {
        'total_absences': total,
        'respectful': respectful,
        'unrespectful': unrespectful,
        'by_reason': by_reason,
    }


def get_teacher_journal_context(group_id: int, subject_id: int, week_offset: int = 0) -> dict:
    """
    Formulates context for teacher journal with week navigation.
    """
    from datetime import timedelta
    from main.models import BuildingAccessLog, StudyGroup, Lesson
    
    # 1. Date Range Handling (Weekly)
    today = date.today()
    # Find Monday of the current week
    start_of_week = today - timedelta(days=today.weekday())
    # Apply offset
    target_monday = start_of_week + timedelta(weeks=week_offset)
    target_sunday = target_monday + timedelta(days=6)
    
    # 2. Basic Info
    group = StudyGroup.objects.get(id=group_id)
    students = User.objects.filter(group=group, role='student').order_by('full_name')

    # 3. RFID Presence (Current Day only or current week? Usually current status)
    access_logs = BuildingAccessLog.objects.filter(
        timestamp__date=today,
        student__in=students
    ).order_by('student', 'timestamp')
    
    presence_map = {s.id: False for s in students}
    student_logs = {}
    for log in access_logs:
        student_logs[log.student_id] = log
    for student_id in presence_map:
        last_log = student_logs.get(student_id)
        if last_log and last_log.action == 'ENTER':
            presence_map[student_id] = True

    # 4. Lessons for the week
    lessons = Lesson.objects.filter(
        group_id=group_id,
        subject_id=subject_id,
        date__range=(target_monday, target_sunday)
    ).order_by('date', 'start_time')

    # Group lessons by date for headers
    # lesson_headers = [ {date, day_name, lessons: [...]}, ... ]
    headers_map = {}
    for lesson in lessons:
        if lesson.date not in headers_map:
            # Ukrainian translation for days
            days_uk = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
            day_name = days_uk[lesson.date.weekday()]
            
            headers_map[lesson.date] = {
                'date': lesson.date,
                'day_name': day_name,
                'lessons': []
            }
        
        # Determine lesson number
        lesson_num = lesson.lesson_number
        
        max_points = getattr(lesson.evaluation_type, 'weight_percent', 10) if lesson.evaluation_type else 12
        print(f"[DEBUG] Header info: date={lesson.date}, day={day_name}, lesson={lesson_num}, max={max_points}")

        headers_map[lesson.date]['lessons'].append({
            'lesson_num': lesson_num,
            'lesson_type': 'Л' if 'Л' in (lesson.topic or '') else 'П', 
            'topic': lesson.topic,
            'max_points': max_points,
            'id': lesson.id
        })

    # Sort headers by date
    lesson_headers = sorted(headers_map.values(), key=lambda x: x['date'])

    # 5. Journal Data (Grades)
    performances = StudentPerformance.objects.filter(
        lesson__in=lessons
    ).select_related('absence', 'lesson')

    # Structure: {student_id: {date: {lesson_num: {value, comment, etc}}}}
    journal_data = {}
    for s in students:
        journal_data[s.id] = {}
        for h in lesson_headers:
            journal_data[s.id][h['date']] = {}

    for perf in performances:
        s_id = perf.student_id
        l_date = perf.lesson.date
        l_num = perf.lesson.lesson_number
        
        if s_id in journal_data and l_date in journal_data[s_id]:
             display_value = ""
             if perf.absence:
                  display_value = perf.absence.code
             elif perf.earned_points is not None:
                  display_value = str(int(perf.earned_points))
             
             journal_data[s_id][l_date][l_num] = {
                 'get_display_value': display_value,
                 'comment': perf.comment,
                 'is_grade': perf.earned_points is not None
             }

    # 6. Students Data with Presence
    students_list = []
    for s in students:
        students_list.append({
            'id': s.id,
            'name': s.full_name,
            'is_in_building': presence_map.get(s.id, False)
        })

    return {
        'group_name': group.name,
        'students': students_list,
        'lesson_headers': lesson_headers,
        'journal_data': journal_data,
        'week_start': target_monday,
        'week_end': target_sunday,
        'week_offset': week_offset,
        'evaluation_types': EvaluationType.objects.filter(assignment__group_id=group_id, assignment__subject_id=subject_id)
    }
