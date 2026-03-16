"""
Grading Service - Business Logic для системи оцінювання

Цей модуль містить функції для:
- Розрахунку оцінок студентів
- Агрегації балів
- Конвертації балів у оцінки за шкалою
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Avg, Count, Sum, Q, QuerySet
from main.models import (
    User, Subject, StudentPerformance, GradingScale, GradeRule,
    Lesson, EvaluationType, AbsenceReason, TeachingAssignment,
)

logger = logging.getLogger(__name__)


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


def save_grade(
    *,
    teacher_id: int,
    student_id: int,
    lesson_id: Optional[int],
    lesson_date_str: Optional[str],
    lesson_num: Optional[int],
    subject_id: Optional[int],
    raw_value,
    absence_id: Optional[int],
    has_absence_id: bool,
    comment_text: Optional[str],
) -> dict:
    """
    Бізнес-логіка збереження оцінки студента.

    Повертає dict: {'status': 'success'|'error', 'message': str}
    """
    from main.constants import DEFAULT_LESSON_TIMES, DEFAULT_TIME_SLOTS

    # 1. Validate inputs
    if not lesson_id and not (student_id and lesson_date_str and lesson_num and subject_id):
        return {
            'status': 'error',
            'message': (
                f'Missing coordinates or lesson_id: '
                f's:{student_id} d:{lesson_date_str} n:{lesson_num} sub:{subject_id}'
            ),
        }

    # 2. Resolve student and group
    student = User.objects.filter(pk=student_id).first()
    if not student:
        return {'status': 'error', 'message': 'Студента не знайдено'}
    group = student.group
    if not group:
        return {'status': 'error', 'message': 'Студент не має групи'}

    # 3. Resolve lesson
    if lesson_id:
        current_lesson = Lesson.objects.filter(id=lesson_id).first()
        if not current_lesson:
            return {'status': 'error', 'message': 'Заняття не знайдено'}
    else:
        start_time_info = DEFAULT_TIME_SLOTS.get(int(lesson_num))
        if start_time_info:
            start_time = start_time_info[0]
        else:
            start_time_str = DEFAULT_LESSON_TIMES.get(int(lesson_num), "08:30")
            start_time = datetime.strptime(start_time_str, "%H:%M").time()

        try:
            assignment = TeachingAssignment.objects.get(
                teacher_id=teacher_id,
                subject_id=int(subject_id),
                group=group,
            )
        except TeachingAssignment.DoesNotExist:
            return {
                'status': 'error',
                'message': (
                    f'Прив\'язку викладача не знайдено: '
                    f'teacher={teacher_id}, subject={subject_id}, group={group.id}'
                ),
            }

        eval_type = assignment.evaluation_types.first()
        if not eval_type:
            eval_type = EvaluationType.objects.create(
                assignment=assignment,
                name="Заняття",
                weight_percent=0,
            )

        current_lesson, created = Lesson.objects.get_or_create(
            group=group,
            date=lesson_date_str,
            start_time=start_time,
            defaults={
                'subject_id': int(subject_id),
                'teacher_id': teacher_id,
                'end_time': (
                    datetime.combine(date.today(), start_time) + timedelta(minutes=90)
                ).time(),
                'evaluation_type': eval_type,
            },
        )

        if not created:
            if current_lesson.subject_id != int(subject_id):
                logger.debug(
                    "Lesson subject conflict: DB=%s, REQ=%s. Updating.",
                    current_lesson.subject_id, subject_id,
                )
                current_lesson.subject_id = int(subject_id)
                current_lesson.teacher_id = teacher_id
                current_lesson.evaluation_type = eval_type
                current_lesson.save()
            elif current_lesson.evaluation_type_id != eval_type.id:
                current_lesson.evaluation_type = eval_type
                current_lesson.save()

    logger.debug(
        "Using Lesson: id=%s, subject=%s, group=%s",
        current_lesson.id, current_lesson.subject_id, current_lesson.group_id,
    )

    # 4. Parse value
    grade_value = None
    absence_obj = None

    if raw_value in [None, '', '—'] and not comment_text:
        StudentPerformance.objects.filter(
            lesson=current_lesson, student_id=student_id
        ).delete()
        return {'status': 'success', 'message': 'Cleared'}

    raw_str = str(raw_value).upper().strip() if raw_value is not None else ""
    if raw_str in ['H', 'N', 'Н']:
        absence_obj = (
            AbsenceReason.objects.filter(code='Н').first()
            or AbsenceReason.objects.first()
        )
    elif absence_id:
        absence_obj = AbsenceReason.objects.filter(id=absence_id).first()
    elif raw_str.isdigit() or (raw_str.startswith('-') and raw_str[1:].isdigit()):
        grade_value = int(raw_str)

    logger.debug(
        "Saving Grade: Student=%s, Lesson=%s, Value=%s",
        student_id, current_lesson.id, raw_value,
    )

    # 5. Build defaults and save
    defaults = {}
    if grade_value is not None:
        defaults['earned_points'] = grade_value
        defaults['absence'] = None
    if has_absence_id or absence_obj:
        defaults['absence'] = absence_obj
        if absence_obj:
            defaults['earned_points'] = None
    if comment_text is not None:
        defaults['comment'] = comment_text

    perf, created = StudentPerformance.objects.update_or_create(
        lesson=current_lesson,
        student_id=student_id,
        defaults=defaults,
    )
    logger.debug("Performance saved: id=%s, created=%s", perf.id, created)

    # --- Сповіщення студента ---
    try:
        from main.models import Notification
        subject_name = current_lesson.subject.name if current_lesson.subject_id else "Предмет"
        lesson_date  = current_lesson.date.strftime('%d.%m.%Y') if current_lesson.date else ''
        if grade_value is not None:
            Notification.objects.create(
                recipient_id=student_id,
                notif_type='grade',
                title=f"Нова оцінка з {subject_name}",
                message=f"{lesson_date}: {grade_value} балів",
            )
        elif absence_obj is not None:
            Notification.objects.create(
                recipient_id=student_id,
                notif_type='absence',
                title=f"Відмічено пропуск з {subject_name}",
                message=f"{lesson_date}: {absence_obj.name} ({absence_obj.code})",
            )
    except Exception:
        logger.exception("save_grade: не вдалося створити сповіщення")

    return {'status': 'success', 'message': 'Saved'}
