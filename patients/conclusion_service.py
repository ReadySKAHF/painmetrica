"""
Сервис формирования строки «Заключение» в консультативном заключении (DOCX).

Публичный интерфейс:
    build_conclusion_text(category, step_scores, step_labels, pain_duration)
        -> (conclusion_text: str, show_recommendations: bool)

Маппинг sidebar_step для комплексного теста:
    1 = ВАШ (VAS)
    2 = DN4
    3 = CSI
    4 = HADS тревога
    5 = HADS депрессия
"""

# ─── Таблицы склонений ────────────────────────────────────────────────────

PAIN_DURATION_DECL = {
    'acute':    'острый',
    'subacute': 'подострый',
    'chronic':  'хронический',
}

VAS_DECL = {
    'Слабый болевой синдром':    'слабый болевой синдром',
    'Умеренный болевой синдром': 'умеренный болевой синдром',
    'Сильный болевой синдром':   'сильный болевой синдром',
}

DN4_DECL = {
    'Нейропатическая боль': 'нейропатического характера',
    'Ноцицептивная боль':   'ноцицептивного характера',
}

CSI_DECL = {
    'Центральная сенситизация — субклиническая': 'с субклиническим уровнем центральной сенситизации',
    'Центральная сенситизация — лёгкая':         'с легким уровнем центральной сенситизации',
    'Центральная сенситизация — умеренная':      'с умеренным уровнем центральной сенситизации',
    'Центральная сенситизация — сильная':        'с сильным уровнем центральной сенситизации',
    'Центральная сенситизация — экстремальная':  'с экстремальным уровнем центральной сенситизации',
}

# (decl_form, verb):  verb = 'выявлен' | 'выявлено' | '' (без глагола)
_PAINAD_DECL = {
    'Боль отсутствует': (
        'боль отсутствует', '',
    ),
    'Слабый по интенсивности болевой синдром': (
        'слабый по интенсивности болевой синдром', 'выявлен',
    ),
    'Умеренный по интенсивности болевой синдром': (
        'умеренный по интенсивности болевой синдром', 'выявлен',
    ),
    'Сильный болевой синдром': (
        'сильный по интенсивности болевой синдром', 'выявлен',
    ),
}

_NCSR_DECL = {
    'Отсутствие какого-либо наблюдаемого ноцицептивного ответа.': (
        'отсутствие какого-либо наблюдаемого ноцицептивного ответа.',
        'выявлено',
    ),
    'Слабый ноцицептивный ответ. Может быть неспецифическим или рефлекторным. Требуется наблюдение, но не всегда указывает на необходимость срочного обезболивания.': (
        'слабый ноцицептивный ответ. Может быть неспецифическим или рефлекторным.'
        ' Требуется наблюдение и повторная оценка.',
        'выявлен',
    ),
    'Умеренный ноцицептивный ответ. Рассматривается как клинически значимый показатель вероятной боли/дискомфорта. Является прямым показанием к оценке текущей анальгезии и, скорее всего, к ее усилению или введению "скоропомощного" анальгетика перед процедурами.': (
        'умеренный ноцицептивный ответ. Требуется введение анальгетика или усиление анальгезии.',
        'выявлен',
    ),
    'Выраженный ноцицептивный ответ. С высокой вероятностью указывает на наличие некупированного болевого синдрома. Требует немедленной коррекции обезболивающей терапии (болюсное введение анальгетика, титрация инфузии) и диагностического поиска причины боли (новое повреждение, осложнение).': (
        'выраженный ноцицептивный ответ. Требуется немедленная коррекция обезболивающей терапии'
        ' (болюсное введение анальгетика, титрация инфузии)'
        ' и диагностический поиск причины боли (новое повреждение, осложнение).',
        'выявлен',
    ),
}

# ─── HADS: текст по диапазонам баллов ────────────────────────────────────

def _hads_sentence(anxiety: int, depression: int) -> str:
    """Полная фраза для HADS по диапазонам баллов (порог клиники = 11+)."""
    anx_none  = anxiety    < 8
    anx_sub   = 8 <= anxiety    < 11
    anx_clin  = anxiety    >= 11
    dep_none  = depression < 8
    dep_sub   = 8 <= depression < 11
    dep_clin  = depression >= 11

    if anx_none  and dep_none:
        return 'У пациента отсутствуют достоверно выраженные признаки тревоги и депрессии.'
    if anx_sub   and dep_none:
        return 'У пациента имеется субклинически выраженная тревога.'
    if anx_clin  and dep_none:
        return 'У пациента имеется клинически выраженная тревога.'
    if anx_none  and dep_sub:
        return 'У пациента имеется субклинически выраженная депрессия.'
    if anx_none  and dep_clin:
        return 'У пациента имеется клинически выраженная депрессия.'
    if anx_sub   and dep_sub:
        return 'У пациента имеется субклинически выраженная тревога и депрессия.'
    if anx_sub   and dep_clin:
        return 'У пациента имеется субклинически выраженная тревога и клинически выраженная депрессия.'
    if anx_clin  and dep_sub:
        return 'У пациента имеется клинически выраженная тревога и субклинически выраженная депрессия.'
    # anx_clin and dep_clin
    return 'У пациента имеется клинически выраженная тревога и депрессия.'


# ─── Вспомогательные ─────────────────────────────────────────────────────

def _decl(table: dict, label: str) -> str | None:
    """Ищет склонённую форму в таблице; возвращает None если не найдено."""
    return table.get(label)


def _is_undefined_subtype(dn4: int, csi: int, hads_anxiety: int, hads_depression: int) -> bool:
    if dn4 < 4 and 30 <= csi <= 39:
        return True
    if dn4 < 4 and csi >= 40 and hads_anxiety < 11 and hads_depression < 11:
        return True
    return False


# ─── Построители по категориям ────────────────────────────────────────────

def _build_complex(
    step_scores: dict,
    step_labels: dict,
    pain_duration: str,
) -> tuple[str, bool]:
    vas             = step_scores.get(1, 0)
    dn4             = step_scores.get(2, 0)
    csi             = step_scores.get(3, 0)
    hads_anxiety    = step_scores.get(4, 0)
    hads_depression = step_scores.get(5, 0)

    required_steps = [1, 2, 3, 4, 5]
    if not all(s in step_scores for s in required_steps):
        return 'Заключение: –', True

    # ── Случай 2 / 3: боль отсутствует ───────────────────────────────
    if vas == 0:
        if hads_anxiety >= 11 or hads_depression >= 11:
            if hads_anxiety >= 11 and hads_depression >= 11:
                hads_part = 'клинически выраженная тревога и депрессия'
            elif hads_anxiety >= 11:
                hads_part = 'клинически выраженная тревога'
            else:
                hads_part = 'клинически выраженная депрессия'
            return (
                f'Заключение: боль отсутствует. У пациента выявлена {hads_part}.',
                True,
            )
        return 'Заключение: боль отсутствует. Лечение болевого синдрома не требуется.', True

    # ── Случай 4: неопределённый подтип ──────────────────────────────
    if _is_undefined_subtype(dn4, csi, hads_anxiety, hads_depression):
        return (
            'Заключение: неопределённый подтип болевого синдрома.'
            ' Рекомендуется повторное тестирование или очная консультация невролога.',
            False,
        )

    # ── Случай 1: VAS > 0, подтип определён ──────────────────────────
    vas_decl = _decl(VAS_DECL, step_labels.get(1, ''))
    dn4_decl = _decl(DN4_DECL, step_labels.get(2, ''))
    csi_decl = _decl(CSI_DECL, step_labels.get(3, ''))

    if not (vas_decl and dn4_decl and csi_decl):
        return 'Заключение: –', True

    dur_decl = PAIN_DURATION_DECL.get(pain_duration, '')
    dur_part = f'{dur_decl} ' if dur_decl else ''

    # Суффикс «высокий риск дисфункциональной боли»
    csi_risk = ''
    if csi > 40 and (hads_anxiety >= 8 or hads_depression >= 8):
        csi_risk = ' (высокий риск дисфункциональной боли)'

    hads_text = _hads_sentence(hads_anxiety, hads_depression)

    conclusion = (
        f'Заключение: у пациента имеется {dur_part}{vas_decl},'
        f' {dn4_decl}, {csi_decl}{csi_risk}. {hads_text}'
    )
    return conclusion, True


def _build_painad(step_scores: dict, step_labels: dict) -> tuple[str, bool]:
    if 1 not in step_scores:
        return 'Заключение: –', True
    label = step_labels.get(1, '')
    entry = _PAINAD_DECL.get(label)
    if not entry:
        decl_form = label[:1].lower() + label[1:] if label else '–'
        return f'Заключение: у пациента выявлен {decl_form}.', True
    decl_form, verb = entry
    if verb:
        return f'Заключение: у пациента {verb} {decl_form}.', True
    return f'Заключение: у пациента {decl_form}.', True


def _build_ncsr(step_scores: dict, step_labels: dict) -> tuple[str, bool]:
    if 1 not in step_scores:
        return 'Заключение: –', True
    label = step_labels.get(1, '')
    entry = _NCSR_DECL.get(label)
    if not entry:
        decl_form = label[:1].lower() + label[1:] if label else '–'
        return f'Заключение: у пациента выявлен {decl_form}.', True
    decl_form, verb = entry
    return f'Заключение: у пациента {verb} {decl_form}', True


# ─── Публичная функция ────────────────────────────────────────────────────

def build_conclusion_text(
    category: str,
    step_scores: dict,
    step_labels: dict,
    pain_duration: str = '',
) -> tuple[str, bool]:
    """Возвращает (conclusion_text, show_recommendations).

    Args:
        category:       'complex' | 'painad' | 'ncsr' | другое
        step_scores:    {sidebar_step: суммарный балл}
        step_labels:    {sidebar_step: ScoreRange.label}
        pain_duration:  'acute' | 'subacute' | 'chronic' | ''

    Returns:
        conclusion_text:      строка для вставки в DOCX
        show_recommendations: False только для Случая 4
    """
    if category == 'complex':
        return _build_complex(step_scores, step_labels, pain_duration)
    if category == 'painad':
        return _build_painad(step_scores, step_labels)
    if category == 'ncsr':
        return _build_ncsr(step_scores, step_labels)

    # Другие тесты — прежнее поведение
    if step_labels:
        labels = [v[:1].lower() + v[1:] for v in step_labels.values() if v]
        return f"Заключение: у пациента имеется {', '.join(labels)}.", True
    return 'Заключение: –', True
