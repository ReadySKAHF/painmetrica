from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from therapy.models import Therapy


@receiver([post_save, post_delete], sender=Therapy)
def invalidate_therapy_cache(sender, **kwargs):
    cache.delete('therapies_ids_all')
