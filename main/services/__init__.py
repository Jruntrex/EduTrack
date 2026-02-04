"""
Service Layer для EduTrack

Цей модуль містить бізнес-логіку додатку, відокремлену від views.
"""

from .grading_service import (
    calculate_student_grade,
    get_bayesian_average,
    convert_points_to_grade,
)

from .schedule_service import (
    validate_schedule_slot,
    check_time_overlap,
    get_schedule_conflicts,
)

__all__ = [
    'calculate_student_grade',
    'get_bayesian_average',
    'convert_points_to_grade',
    'validate_schedule_slot',
    'check_time_overlap',
    'get_schedule_conflicts',
]
