from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


User = get_user_model()


def _default_role_for(user: settings.AUTH_USER_MODEL) -> str:
    if user.is_superuser:
        return UserProfile.Role.ADMIN
    return UserProfile.Role.USER


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)

    expected_role = _default_role_for(instance)
    updated_fields = []

    if instance.is_superuser and profile.role != expected_role:
        profile.role = expected_role
        updated_fields.append("role")

    if created or updated_fields:
        profile.save(update_fields=updated_fields or None)
