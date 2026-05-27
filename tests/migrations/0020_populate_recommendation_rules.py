from django.db import migrations

RULES = [
    # ── Комплексный тест: ВАШ = 0 ──────────────────────────────────────────
    {
        'rule_key': 'complex_vas0_anxiety_only',
        'description': 'Комплексный: ВАШ=0, тревога HADS>11, депрессия≤11',
        'med_ids': [62, 64, 65, 66, 67, 68, 71, 72, 6, 8, 7],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_vas0_depression_only',
        'description': 'Комплексный: ВАШ=0, депрессия HADS>11, тревога≤11',
        'med_ids': [67, 68, 71, 72, 6, 8, 7, 69, 70],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_vas0_both_hads',
        'description': 'Комплексный: ВАШ=0, оба показателя HADS>11',
        'med_ids': [62, 64, 65, 66, 67, 68, 71, 72, 6, 8, 7, 69, 70],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_vas0_rehab',
        'description': 'Комплексный: ВАШ=0, реабилитация при HADS>11',
        'med_ids': [],
        'therapy_ids': [15],
    },
    # ── Комплексный тест: ноцицептивный вариант ─────────────────────────────
    {
        'rule_key': 'complex_nociceptive_vas_1_3',
        'description': 'Комплексный: ноцицептивный вариант, ВАШ 1–3',
        'med_ids': [18, 34, 27, 30, 21, 28, 32, 31, 38, 39, 23],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_nociceptive_vas_4_6',
        'description': 'Комплексный: ноцицептивный вариант, ВАШ 4–6',
        'med_ids': [18, 34, 27, 25, 30, 28, 42, 41, 20, 17, 43, 44, 45,
                    38, 39, 47, 21, 48, 49, 50, 53, 52, 32, 31, 54, 55, 22],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_nociceptive_vas_7_10',
        'description': 'Комплексный: ноцицептивный вариант, ВАШ 7–10',
        'med_ids': [43, 44, 45, 48, 49, 41, 56, 57, 58],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_nociceptive_rehab',
        'description': 'Комплексный: ноцицептивный вариант, реабилитация',
        'med_ids': [],
        'therapy_ids': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    },
    # ── Комплексный тест: нейропатический вариант ───────────────────────────
    {
        'rule_key': 'complex_neuropathic_base',
        'description': 'Комплексный: нейропатический вариант, базовые препараты',
        'med_ids': [12, 13, 14, 6, 7, 8, 15],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_neuropathic_vas_gt3',
        'description': 'Комплексный: нейропатический вариант, доп. при ВАШ>3',
        'med_ids': [48, 49, 50],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_neuropathic_rehab',
        'description': 'Комплексный: нейропатический вариант, реабилитация',
        'med_ids': [],
        'therapy_ids': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    },
    # ── Комплексный тест: дисфункциональный вариант ─────────────────────────
    {
        'rule_key': 'complex_dysfunctional_meds',
        'description': 'Комплексный: дисфункциональный вариант, препараты',
        'med_ids': [6, 7, 8, 12, 13, 14],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_dysfunctional_rehab',
        'description': 'Комплексный: дисфункциональный вариант, реабилитация',
        'med_ids': [],
        'therapy_ids': [15, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    },
    # ── Комплексный тест: смешанный вариант ─────────────────────────────────
    {
        'rule_key': 'complex_mixed_vas_1_3',
        'description': 'Комплексный: смешанный вариант, ВАШ 1–3',
        'med_ids': [18, 34, 27, 30, 21, 28, 32, 31, 38, 39,
                    12, 13, 14, 6, 7, 8, 15, 23],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_mixed_vas_4_6',
        'description': 'Комплексный: смешанный вариант, ВАШ 4–6',
        'med_ids': [18, 34, 27, 25, 30, 28, 42, 41, 20, 17, 43, 44, 45,
                    38, 39, 47, 21, 48, 49, 50, 53, 52, 32, 31, 54, 55, 22,
                    12, 13, 14, 6, 7, 8, 15],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_mixed_vas_7_10',
        'description': 'Комплексный: смешанный вариант, ВАШ 7–10',
        'med_ids': [43, 44, 45, 48, 41, 56, 57, 58, 12, 13, 14, 6, 7, 8, 15],
        'therapy_ids': [],
    },
    {
        'rule_key': 'complex_mixed_rehab',
        'description': 'Комплексный: смешанный вариант, реабилитация',
        'med_ids': [],
        'therapy_ids': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    },
    # ── Общий аддон: хроническая боль > 3 мес ───────────────────────────────
    {
        'rule_key': 'complex_chronic_addon',
        'description': 'Комплексный: хроническая боль (>3 мес), доп. препараты',
        'med_ids': [12, 13, 6, 7, 8],
        'therapy_ids': [],
    },
    # ── PAINAD ──────────────────────────────────────────────────────────────
    {
        'rule_key': 'painad_1_3',
        'description': 'PAINAD: 1–3 балла',
        'med_ids': [18, 34, 27, 30, 21, 28, 32, 31, 38, 39],
        'therapy_ids': [],
    },
    {
        'rule_key': 'painad_4_6',
        'description': 'PAINAD: 4–6 баллов',
        'med_ids': [18, 34, 27, 25, 30, 28, 42, 41, 20, 17, 43, 44,
                    38, 39, 47, 21, 48, 49, 50, 53, 52, 32, 31, 54, 55, 22],
        'therapy_ids': [],
    },
    {
        'rule_key': 'painad_7_10',
        'description': 'PAINAD: 7–10 баллов',
        'med_ids': [43, 44, 48, 41, 56, 57, 58],
        'therapy_ids': [],
    },
    {
        'rule_key': 'painad_rehab',
        'description': 'PAINAD: реабилитация (1–10 баллов)',
        'med_ids': [],
        'therapy_ids': [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
    },
    # ── NCS-R ───────────────────────────────────────────────────────────────
    {
        'rule_key': 'ncsr_3_4',
        'description': 'NCS-R: 3–4 балла',
        'med_ids': [26, 28, 24, 42, 19, 16, 53, 60, 40],
        'therapy_ids': [],
    },
    {
        'rule_key': 'ncsr_5_plus',
        'description': 'NCS-R: 5+ баллов',
        'med_ids': [26, 28, 24, 42, 19, 16, 53, 60, 40, 51, 46],
        'therapy_ids': [],
    },
]


def populate_rules(apps, schema_editor):
    RecommendationRule = apps.get_model('tests', 'RecommendationRule')
    Medication = apps.get_model('medications', 'Medication')
    Therapy = apps.get_model('therapy', 'Therapy')

    for rule_data in RULES:
        rule, _ = RecommendationRule.objects.get_or_create(
            rule_key=rule_data['rule_key'],
            defaults={'description': rule_data['description']},
        )
        if rule_data['med_ids']:
            meds = Medication.objects.filter(pk__in=rule_data['med_ids'])
            rule.medications.set(meds)
        if rule_data['therapy_ids']:
            therapies = Therapy.objects.filter(pk__in=rule_data['therapy_ids'])
            rule.therapies.set(therapies)


def depopulate_rules(apps, schema_editor):
    RecommendationRule = apps.get_model('tests', 'RecommendationRule')
    keys = [r['rule_key'] for r in RULES]
    RecommendationRule.objects.filter(rule_key__in=keys).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0019_add_recommendation_rule'),
    ]

    operations = [
        migrations.RunPython(populate_rules, depopulate_rules),
    ]
