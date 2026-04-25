from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Получение значения словаря по ключу в шаблоне.
    Использование: {{ my_dict|get_item:key }}
    """
    if not isinstance(dictionary, dict):
        return None
    # Пробуем варианты ключа: q_{key}, строковый, исходный
    val = dictionary.get(f'q_{key}')
    if val is None:
        val = dictionary.get(str(key))
    if val is None:
        val = dictionary.get(key)
    return val


@register.filter
def scale_label(question, value):
    """Возвращает текстовую метку шкалы для заданного числового значения.
    Использование: {{ answer.question|scale_label:answer.scale_value }}
    """
    if value is None:
        return '—'
    try:
        int_val = int(value)
    except (TypeError, ValueError):
        return str(value)
    for lbl in (question.scale_labels or []):
        try:
            if int(lbl.get('min', 0)) <= int_val <= int(lbl.get('max', 0)):
                return lbl.get('label', '—')
        except (TypeError, ValueError):
            continue
    return str(value)


@register.filter
def is_selected(saved_answers, option_pk):
    """Проверяет, выбран ли вариант ответа.
    Использование: {{ saved_answers|is_selected:option.pk }}
    """
    if not isinstance(saved_answers, dict):
        return False
    for val in saved_answers.values():
        if isinstance(val, list):
            if option_pk in val or str(option_pk) in [str(v) for v in val]:
                return True
        elif str(val) == str(option_pk):
            return True
    return False
