from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from medications.models import Medication, MedicationNote


@receiver([post_save, post_delete], sender=Medication)
def invalidate_medication_cache(sender, instance, **kwargs):
    cache.delete_many([
        f'medication:{instance.pk}',
        'medications_all',
        'medications_ids_all',
    ])


@receiver(post_save, sender=MedicationNote)
def invalidate_note_cache(sender, instance, **kwargs):
    cache.delete(f'med_note_{instance.medication_id}_{instance.doctor_id}')


@receiver(post_delete, sender=MedicationNote)
def invalidate_note_cache_on_delete(sender, instance, **kwargs):
    cache.delete(f'med_note_{instance.medication_id}_{instance.doctor_id}')
