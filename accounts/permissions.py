from __future__ import annotations

from django.contrib.auth import get_user_model

from .models import UserProfile


User = get_user_model()


def get_or_create_profile(user: User) -> UserProfile | None:
    if not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if user.is_superuser and profile.role != UserProfile.Role.ADMIN:
        profile.role = UserProfile.Role.ADMIN
        profile.save(update_fields=["role", "updated_at"])
    return profile


def get_role(user: User) -> str:
    if not user.is_authenticated:
        return UserProfile.Role.USER
    if user.is_superuser:
        return UserProfile.Role.ADMIN
    profile = get_or_create_profile(user)
    return profile.role if profile else UserProfile.Role.USER


def is_support(user: User) -> bool:
    return user.is_staff and get_role(user) == UserProfile.Role.SUPPORT


def can_manage_companies(user: User) -> bool:
    role = get_role(user)
    return user.is_superuser or role == UserProfile.Role.ADMIN
