from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CampaignForm
from .models import Campaign


@login_required
def campaign_list(request):
    campaigns = Campaign.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "campaigns/campaign_list.html", {"campaigns": campaigns})


@login_required
def campaign_create(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.user = request.user
            campaign.save()
            messages.success(request, "Кампания создана.")
            return redirect("campaigns:list")
    else:
        form = CampaignForm()
    return render(request, "campaigns/campaign_form.html", {"form": form, "mode": "create"})


@login_required
def campaign_edit(request, campaign_id: int):
    campaign = get_object_or_404(Campaign, pk=campaign_id, user=request.user)
    if request.method == "POST":
        form = CampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            messages.success(request, "Кампания обновлена.")
            return redirect("campaigns:list")
    else:
        form = CampaignForm(instance=campaign)
    return render(request, "campaigns/campaign_form.html", {"form": form, "mode": "edit", "campaign": campaign})


@login_required
def campaign_delete(request, campaign_id: int):
    campaign = get_object_or_404(Campaign, pk=campaign_id, user=request.user)
    if request.method == "POST":
        campaign.delete()
        messages.success(request, "Кампания удалена.")
        return redirect("campaigns:list")
    return render(request, "campaigns/campaign_confirm_delete.html", {"campaign": campaign})
