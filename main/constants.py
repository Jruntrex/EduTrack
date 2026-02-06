"""
Constants для EduTrack

Цей модуль містить всі константи проекту:
- Ролі користувачів
- Дні тижня
- Часові слоти (дзвінки)
- Коди пропусків
"""

from enum import Enum
from datetime import time


class UserRole(str, Enum):
    """Ролі користувачів у системі."""
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'
    
    @classmethod
    def choices(cls):
        """Для використання в Django моделях."""
        return [(role.value, role.name.title()) for role in cls]


class DayOfWeek(int, Enum):
    """Дні тижня (ISO стандарт: 1=Понеділок, 7=Неділя)."""
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7
    
    @classmethod
    def get_name_uk(cls, day: int) -> str:
        """Отримати українську назву дня."""
        names = {
            1: 'Понеділок',
            2: 'Вівторок',
            3: 'Середа',
            4: 'Четвер',
            5: 'П\'ятниця',
            6: 'Субота',
            7: 'Неділя',
        }
        return names.get(day, '')
    
    @classmethod
    def get_short_name_uk(cls, day: int) -> str:
        """Отримати скорочену українську назву дня."""
        names = {
            1: 'Пн',
            2: 'Вт',
            3: 'Ср',
            4: 'Чт',
            5: 'Пт',
            6: 'Сб',
            7: 'Нд',
        }
        return names.get(day, '')


# Стандартний розклад дзвінків
# Формат: номер_пари -> (час_початку, час_кінця)
DEFAULT_TIME_SLOTS = {
    1: (time(8, 30), time(10, 0)),
    2: (time(10, 0), time(11, 30)),
    3: (time(11, 40), time(13, 10)),
    4: (time(13, 30), time(15, 0)),
    5: (time(15, 0), time(16, 30)),
    6: (time(16, 40), time(18, 10)),
    7: (time(18, 20), time(19, 50)),
    8: (time(20, 0), time(21, 30)),
}

# Альтернативний формат (для зворотної сумісності)
# ПОПЕРЕДЖЕННЯ: Використовуйте DEFAULT_TIME_SLOTS для нових розробок
DEFAULT_LESSON_TIMES = {
    1: "08:30",
    2: "10:00",
    3: "11:40",
    4: "13:30",
    5: "15:00",
}

# Тривалість стандартної пари (хвилини)
DEFAULT_LESSON_DURATION = 80


class AbsenceCode(str, Enum):
    """Коди пропусків."""
    ABSENT = 'Н'  # Неповажна причина
    DISTANCE = 'ДЛ'  # Дистанційне навчання
    VALID_REASON = 'ПП'  # Поважна причина
    SICK = 'Б'  # Хвороба
    VACATION = 'В'  # Відпустка
    
    @classmethod
    def get_code_value(cls, code: str) -> int:
        """Конвертація коду у числове значення (для старої системи)."""
        mapping = {
            'Н': -1,
            'ДЛ': -2,
            'ПП': -3,
            'Б': -4,
            'В': -5,
        }
        return mapping.get(code, -1)
    
    @classmethod
    def get_value_code(cls, value: int) -> str:
        """Конвертація числового значення у код (для старої системи)."""
        mapping = {
            -1: 'Н',
            -2: 'ДЛ',
            -3: 'ПП',
            -4: 'Б',
            -5: 'В',
        }
        return mapping.get(value, 'Н')


# Мінімальний та максимальний бал
MIN_GRADE = 0
MAX_GRADE = 100

# Бали для оцінок ЄКТС
ECTS_GRADE_THRESHOLDS = {
    'A': 90,  # Відмінно
    'B': 80,  # Дуже добре
    'C': 70,  # Добре
    'D': 60,  # Задовільно
    'E': 50,  # Достатньо
    'FX': 35, # Незадовільно (з можливістю перескладання)
    'F': 0,   # Незадовільно (без можливості перескладання)
}

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Формати дат
DATE_FORMAT_SHORT = '%d.%m'
DATE_FORMAT_FULL = '%d.%m.%Y'
DATE_FORMAT_ISO = '%Y-%m-%d'
TIME_FORMAT = '%H:%M'
