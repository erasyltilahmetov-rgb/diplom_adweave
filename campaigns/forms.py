from django import forms

from .models import Campaign, CompanyApplication


class CompanyApplicationForm(forms.ModelForm):
    class Meta:
        model = CompanyApplication
        fields = [
            "company_name",
            "contact_person",
            "iin_bin",
            "email",
            "phone",
            "address",
            "comment",
        ]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_iin_bin(self):
        value = (self.cleaned_data.get("iin_bin") or "").strip()
        digits_only = "".join(ch for ch in value if ch.isdigit())
        if len(digits_only) != 12:
            raise forms.ValidationError("ИИН/БИН должен содержать 12 цифр.")
        return digits_only


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "description", "status", "start_date", "end_date"]
        labels = {
            "name": "Название кампании",
            "description": "Описание",
            "status": "Статус",
            "start_date": "Дата старта",
            "end_date": "Дата окончания",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
