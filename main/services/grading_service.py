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
from main.models import User, Subject, StudentPerformance, GradingScale, GradeRule, Lesson


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
