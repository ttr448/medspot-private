from django import forms

from .models import Pharmacy
from .working_hours import parse_working_hours


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

    def clean_working_hours(self):
        value = (self.cleaned_data.get("working_hours") or "").strip()
        if value:
            try:
                parse_working_hours(value)
            except ValueError as error:
                raise forms.ValidationError(str(error))
        return value
