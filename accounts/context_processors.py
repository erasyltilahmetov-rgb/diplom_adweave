from .models import UserProfile
from .permissions import get_or_create_profile, get_role


def user_profile(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    profile = get_or_create_profile(user)
    role_code = get_role(user)

    role_labels = {
        UserProfile.Role.ADMIN: "admin",
        UserProfile.Role.SUPPORT: "support",
        UserProfile.Role.USER: "user",
    }

    plan_labels = {
        UserProfile.Plan.BASIC: "basic",
        UserProfile.Plan.STANDARD: "standard",
    }

    return {
        "user_profile": profile,
        "user_role_code": role_code,
        "user_role_label": role_labels.get(role_code, "user"),
        "user_plan_code": profile.effective_plan,
        "user_plan_label": plan_labels.get(profile.effective_plan, "basic"),
        "user_can_apply_company": profile.can_submit_company_application,
        "user_daily_threads_limit": profile.daily_threads_limit,
        "user_trial_active": profile.trial_active,
        "campaign_urls": ("campaign_list", "campaign_create", "campaign_edit", "campaign_delete"),
    }
