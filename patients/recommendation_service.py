from dataclasses import dataclass, field
from typing import Set


@dataclass
class RecommendationContext:
    recommended_med_ids: Set[int] = field(default_factory=set)
    recommended_therapy_ids: Set[int] = field(default_factory=set)
    show_meds_page: bool = True
    show_rehab_page: bool = True


def get_recommendation_context(patient, last_result) -> RecommendationContext:
    """Возвращает контекст рекомендаций для пациента на основе последнего результата."""
    if last_result is None:
        return RecommendationContext()

    from django.core.cache import cache
    cache_key = f'rec_ctx_{last_result.pk}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    category = getattr(last_result.test, 'category', '')

    if category == 'complex':
        result = _context_for_complex(patient, last_result)
    elif category == 'painad':
        result = _context_for_painad(last_result)
    elif category == 'ncsr':
        result = _context_for_ncsr(last_result)
    else:
        result = RecommendationContext()

    cache.set(cache_key, result, 3600)
    return result


# ─────────────────────────────────────────────────────────────────────────────

def _get_scores_by_step(result):
    """Вычисляет суммарные баллы по каждому sidebar_step из ответов TestResult."""
    step_scores = {}
    for answer in result.answers.select_related('question__stage'):
        step = answer.question.stage.sidebar_step
        step_scores[step] = step_scores.get(step, 0) + answer.score
    return step_scores


def _collect_from_rules(rule_keys):
    """Собирает уникальные ID лекарств и мероприятий по списку ключей правил."""
    from tests.models import RecommendationRule

    med_ids: Set[int] = set()
    therapy_ids: Set[int] = set()

    rules = (
        RecommendationRule.objects
        .filter(rule_key__in=rule_keys)
        .prefetch_related('medications', 'therapies')
    )
    for rule in rules:
        med_ids.update(rule.medications.values_list('pk', flat=True))
        therapy_ids.update(rule.therapies.values_list('pk', flat=True))

    return med_ids, therapy_ids


# ─────────────────────────────────────────────────────────────────────────────

def _context_for_complex(patient, result) -> RecommendationContext:
    scores = _get_scores_by_step(result)
    vas = scores.get(1, 0)
    dn4 = scores.get(2, 0)
    csi = scores.get(3, 0)
    hads_a = scores.get(4, 0)
    hads_d = scores.get(5, 0)
    is_chronic = patient.pain_duration == 'chronic'

    rule_keys = []

    # ── ВАШ = 0 ──────────────────────────────────────────────────────────────
    if vas == 0:
        if hads_a > 11 or hads_d > 11:
            if hads_a > 11 and hads_d > 11:
                rule_keys.append('complex_vas0_both_hads')
            elif hads_a > 11:
                rule_keys.append('complex_vas0_anxiety_only')
            else:
                rule_keys.append('complex_vas0_depression_only')
            rule_keys.append('complex_vas0_rehab')
            med_ids, therapy_ids = _collect_from_rules(rule_keys)
            return RecommendationContext(
                recommended_med_ids=med_ids,
                recommended_therapy_ids=therapy_ids,
            )
        # ВАШ=0, HADS не превышен — лечение не требуется
        return RecommendationContext(show_meds_page=False, show_rehab_page=False)

    # ── ВАШ > 0: определяем подтип ───────────────────────────────────────────
    if dn4 >= 4 and csi >= 30:
        pathotype = 'mixed'
    elif dn4 >= 4:
        pathotype = 'neuropathic'
    elif csi < 30:
        pathotype = 'nociceptive'
    elif 30 <= csi <= 39:
        pathotype = 'undefined'
    elif csi >= 40 and (hads_a >= 11 or hads_d >= 11):
        pathotype = 'dysfunctional'
    else:
        pathotype = 'undefined'

    if pathotype == 'undefined':
        return RecommendationContext(show_meds_page=False, show_rehab_page=False)

    if pathotype == 'nociceptive':
        if vas <= 3:
            rule_keys.append('complex_nociceptive_vas_1_3')
        elif vas <= 6:
            rule_keys.append('complex_nociceptive_vas_4_6')
        else:
            rule_keys.append('complex_nociceptive_vas_7_10')
        rule_keys.append('complex_nociceptive_rehab')

    elif pathotype == 'neuropathic':
        rule_keys.append('complex_neuropathic_base')
        if vas > 3:
            rule_keys.append('complex_neuropathic_vas_gt3')
        rule_keys.append('complex_neuropathic_rehab')

    elif pathotype == 'dysfunctional':
        rule_keys.append('complex_dysfunctional_meds')
        rule_keys.append('complex_dysfunctional_rehab')

    elif pathotype == 'mixed':
        if vas <= 3:
            rule_keys.append('complex_mixed_vas_1_3')
        elif vas <= 6:
            rule_keys.append('complex_mixed_vas_4_6')
        else:
            rule_keys.append('complex_mixed_vas_7_10')
        rule_keys.append('complex_mixed_rehab')

    if is_chronic:
        rule_keys.append('complex_chronic_addon')

    med_ids, therapy_ids = _collect_from_rules(rule_keys)
    return RecommendationContext(
        recommended_med_ids=med_ids,
        recommended_therapy_ids=therapy_ids,
    )


def _context_for_painad(result) -> RecommendationContext:
    score = result.total_score

    if score == 0:
        return RecommendationContext(show_meds_page=False, show_rehab_page=False)

    if score <= 3:
        rule_keys = ['painad_1_3', 'painad_rehab']
    elif score <= 6:
        rule_keys = ['painad_4_6', 'painad_rehab']
    else:
        rule_keys = ['painad_7_10', 'painad_rehab']

    med_ids, therapy_ids = _collect_from_rules(rule_keys)
    return RecommendationContext(
        recommended_med_ids=med_ids,
        recommended_therapy_ids=therapy_ids,
    )


def _context_for_ncsr(result) -> RecommendationContext:
    score = result.total_score

    if score <= 2:
        return RecommendationContext(show_meds_page=False, show_rehab_page=False)

    rule_keys = ['ncsr_3_4'] if score <= 4 else ['ncsr_5_plus']
    med_ids, therapy_ids = _collect_from_rules(rule_keys)
    return RecommendationContext(
        recommended_med_ids=med_ids,
        recommended_therapy_ids=therapy_ids,
        show_rehab_page=False,
    )
