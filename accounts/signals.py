import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver
from accounts.models import DoctorProfile

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=DoctorProfile)
def send_verification_email_on_org_assigned(sender, instance, **kwargs):
    """Отправляет письмо доктору когда ему впервые назначается организация (верификация)."""
    if not instance.pk:
        return
    try:
        old = DoctorProfile.objects.get(pk=instance.pk)
    except DoctorProfile.DoesNotExist:
        return
    if old.organization_id is None and instance.organization_id is not None:
        try:
            from accounts.services.email_service import send_verification_email
            send_verification_email(instance.user)
        except Exception as e:
            logger.error("Ошибка отправки письма верификации для %s: %s", instance.user.email, e)
