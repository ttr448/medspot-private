from django import forms

from .models import Pharmacy


class PharmacyWorkingHoursForm(forms.ModelForm):
    class Meta:
        model = Pharmacy
        fields = ["working_hours"]
        labels = {"working_hours": "Working hours"}
        widgets = {
            "working_hours": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Example: Sat-Thu 08:00-22:00; Fri 16:00-22:00",
                }
            )
        }
