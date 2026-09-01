# inventory/forms.py
"""
Sprint 2 forms for inventory CRUD.

Two separate forms rather than one shared form, because Add and Edit need
different fields:
  - Add needs the full medicine description (it may be creating a brand
    new Medicine catalog entry).
  - Edit only touches this pharmacy's stock numbers (quantity and
    minimum_threshold), per the Sprint 2 requirement ("at minimum, update
    quantity / minimum threshold").
"""
from django import forms


class AddMedicineForm(forms.Form):
    name = forms.CharField(max_length=255, label="Medicine name")
    category = forms.CharField(max_length=255, required=False)
    active_ingredient = forms.CharField(max_length=255, required=False)
    dosage_form = forms.CharField(max_length=100, required=False, label="Dosage form (e.g. tablet, syrup)")
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
    quantity = forms.IntegerField(min_value=0)
    minimum_threshold = forms.IntegerField(min_value=0, required=False, initial=0)

    def clean_minimum_threshold(self):
        value = self.cleaned_data.get("minimum_threshold")
        return value if value is not None else 0
