# inventory/forms.py
"""
Forms for adding medicines, editing stock, and importing medicine lists.
"""
from pathlib import Path

from django import forms


class AddMedicineForm(forms.Form):
    name = forms.CharField(max_length=255, label="Medicine name")
    category = forms.CharField(max_length=255, required=False)
    active_ingredient = forms.CharField(max_length=255, required=False)
    strength = forms.CharField(max_length=100, label="Strength (e.g. 500 mg)")
    quantity = forms.IntegerField(min_value=0)
    minimum_threshold = forms.IntegerField(min_value=0, required=False, initial=0)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Medicine name is required.")
        return name

    def clean_minimum_threshold(self):
        value = self.cleaned_data.get("minimum_threshold")
        return value if value is not None else 0


class EditInventoryForm(forms.Form):
    PROFILE_FIELDS = ("name", "active_ingredient", "category", "strength")

    name = forms.CharField(
        max_length=255,
        required=False,
        label="Medicine name",
    )
    active_ingredient = forms.CharField(
        max_length=255,
        required=False,
        label="Active ingredient",
    )
    category = forms.CharField(max_length=255, required=False)
    strength = forms.CharField(
        max_length=100,
        required=False,
        label="Strength (e.g. 500 mg)",
    )
    quantity = forms.IntegerField(min_value=0, label="Available quantity")
    minimum_threshold = forms.IntegerField(
        min_value=0,
        required=False,
        initial=0,
        label="Minimum stock threshold",
    )

    def clean(self):
        cleaned_data = super().clean()
        self.profile_submitted = any(
            field in self.data for field in self.PROFILE_FIELDS
        )

        if self.profile_submitted:
            medicine_name = (cleaned_data.get("name") or "").strip()
            if not medicine_name:
                self.add_error("name", "Medicine name is required.")
            else:
                cleaned_data["name"] = medicine_name

            for field in ("active_ingredient", "category", "strength"):
                cleaned_data[field] = (cleaned_data.get(field) or "").strip()

        return cleaned_data

    def clean_minimum_threshold(self):
        value = self.cleaned_data.get("minimum_threshold")
        return value if value is not None else 0


class BatchUploadForm(forms.Form):
    file = forms.FileField(
        label="CSV or Excel file",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".csv,.xlsx"}
        ),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in {".csv", ".xlsx"}:
            raise forms.ValidationError("Only .csv and .xlsx files are supported.")

        if uploaded_file.size == 0:
            raise forms.ValidationError("The selected file is empty.")

        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("The file must not exceed 5 MB.")

        return uploaded_file
