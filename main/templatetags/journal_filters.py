# main/templatetags/journal_filters.py
import json
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if not dictionary: return None
    try: return dictionary.get(key)
    except AttributeError: return getattr(dictionary, key, None)

@register.simple_tag
def get_lesson_at(lessons, date_obj, lesson_num):
    """Шукає урок для конкретної дати та номеру пари."""
    times = {
        1: "08:30",
        2: "10:15",
        3: "12:15",
        4: "14:15",
        5: "16:00",
        6: "17:45"
    }
    target_time = times.get(int(lesson_num))
    if not target_time or not lessons: return None
    
    for l in lessons:
        try:
            if l.date == date_obj and l.start_time.strftime('%H:%M') == target_time:
                return l
        except:
            continue
    return None

@register.simple_tag
def lesson_hours(num):
    """Повертає часовий інтервал для номеру пари."""
    times = {
        1: "08:30 - 09:50",
        2: "10:15 - 11:35",
        3: "12:15 - 13:35",
        4: "14:15 - 15:35",
        5: "16:00 - 17:20",
        6: "17:45 - 19:05"
    }
    return times.get(int(num), "")

@register.filter
def format_teacher_short(full_name):
    """Форматує ПІБ: Прізвище І. О."""
    if not full_name: return ""
    parts = full_name.split()
    if len(parts) >= 2:
        res = f"{parts[0]} {parts[1][0]}."
        if len(parts) >= 3:
            res += f" {parts[2][0]}."
        return res
    return full_name

@register.filter
def to_json(value):
    if value is None: return 'null'
    return json.dumps(value)

@register.filter
def is_equal(value, arg):
    return str(value) == str(arg)

@register.filter
def split(value, arg):
    return str(value).split(arg)

@register.filter
def modulo(value, arg):
    try:
        return int(value) % int(arg)
    except:
        return 0

# Dummy filters for compatibility with old templates if any
@register.filter
def time_to_offset(val, arg=0): return 0
@register.filter
def duration_to_height(val): return 90