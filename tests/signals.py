from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from tests.models import Question, QuestionOption, ScoreRange, Stage, Test


@receiver([post_save, post_delete], sender=Test)
def invalidate_test_cache(sender, instance, **kwargs):
    cache.delete_many([
        f'test_stages:{instance.pk}',
        f'score_ranges:{instance.pk}',
        'active_tests',
    ])


@receiver([post_save, post_delete], sender=Stage)
def invalidate_stage_cache(sender, instance, **kwargs):
    cache.delete(f'test_stages:{instance.test_id}')
    cache.delete(f'stage_questions:{instance.pk}')


@receiver([post_save, post_delete], sender=Question)
def invalidate_question_cache(sender, instance, **kwargs):
    cache.delete(f'stage_questions:{instance.stage_id}')


@receiver([post_save, post_delete], sender=QuestionOption)
def invalidate_option_cache(sender, instance, **kwargs):
    try:
        cache.delete(f'stage_questions:{instance.question.stage_id}')
    except Exception:
        pass


@receiver([post_save, post_delete], sender=ScoreRange)
def invalidate_score_range_cache(sender, instance, **kwargs):
    cache.delete(f'score_ranges:{instance.test_id}')
