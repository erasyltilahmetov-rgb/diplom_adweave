from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.models import UserProfile
from accounts.permissions import get_or_create_profile, get_role

from .forms import CompanyApplicationForm


def company_application_create(request):
    if request.user.is_authenticated:
        profile = get_or_create_profile(request.user)
        role = get_role(request.user)
        is_basic_user = profile and profile.plan == UserProfile.Plan.BASIC
        is_privileged = role in {UserProfile.Role.ADMIN, UserProfile.Role.SUPPORT}
        if is_basic_user and not is_privileged:
            messages.error(
                request,
                "На базовом тарифе нельзя подать заявку на компанию. Выберите тариф выше.",
            )
            return redirect("pricing")

    if request.method == "POST":
        form = CompanyApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            if request.user.is_authenticated:
                application.applicant_user = request.user
            application.save()
            messages.success(request, "Заявка отправлена. Мы свяжемся с вами после проверки.")
            return redirect("company_application_success")
    else:
        form = CompanyApplicationForm()

    return render(request, "campaigns/company_application_form.html", {"form": form})


def company_application_success(request):
    return render(request, "campaigns/company_application_success.html")
