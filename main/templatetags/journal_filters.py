# main/templatetags/journal_filters.py
import json

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Повертає значення словника/об'єкта за ключем."""
    if not dictionary:
        return None
    try:
        return dictionary.get(key)
    except AttributeError:
        # Для об'єктів Django
        return getattr(dictionary, key, None)


@register.filter
def to_json(value):
    """Конвертує Python об'єкт в JSON строку."""
    if value is None:
        return 'null'
    return json.dumps(value)


@register.filter
def is_equal(value, arg):
    """Порівнює два значення, приводячи їх до рядків."""
    return str(value) == str(arg)