from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from medications.models import Medication


@receiver([post_save, post_delete], sender=Medication)
def invalidate_medication_cache(sender, instance, **kwargs):
    cache.delete_many([
        f'medication:{instance.pk}',
        'medications_all',
    ])
