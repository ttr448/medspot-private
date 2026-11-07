"""CSV and XLSX import helpers for a pharmacist's medicine availability."""

import csv
import io
from zipfile import BadZipFile

from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from alerts.services import update_low_stock_alert
from medicines.models import Medicine

from .forms import AddMedicineForm
from .models import Inventory
from .services import inventory_snapshot, record_inventory_change


MAX_IMPORT_ROWS = 500
REQUIRED_COLUMNS = {"name", "strength", "quantity"}
OPTIONAL_COLUMNS = {
    "active_ingredient",
    "category",
    "minimum_threshold",
}
FORM_COLUMNS = (
    "name",
    "active_ingredient",
    "category",
    "strength",
    "quantity",
    "minimum_threshold",
)


class BatchUploadError(Exception):
    """An upload error that can be shown safely on the upload page."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def _cell_text(value):
    """Convert CSV/Excel cell values into strings suitable for Django forms."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalise_headers(values):
    headers = []
    for value in values:
        header = _cell_text(value).lower().replace(" ", "_").replace("-", "_")
        if header == "medicine_name":
            header = "name"
        elif header == "minimum_stock_threshold":
            header = "minimum_threshold"
        headers.append(header)
    return headers


def _validate_rows(headers, raw_rows):
    if not headers or not any(headers):
        raise BatchUploadError(["The file is empty or does not contain a header row."])

    if len(headers) != len(set(headers)):
        raise BatchUploadError(["The file contains duplicate column names."])

    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise BatchUploadError([
            "Missing required columns: " + ", ".join(sorted(missing)) + "."
        ])

    valid_rows = []
    errors = []
    seen = set()
    nonempty_count = 0

    for row_number, values in raw_rows:
        values = list(values or [])
        if not any(_cell_text(value) for value in values):
            continue

        nonempty_count += 1
        if nonempty_count > MAX_IMPORT_ROWS:
            errors.append(
                f"The file exceeds the maximum of {MAX_IMPORT_ROWS} medicine rows."
            )
            break

        row_data = {}
        for index, header in enumerate(headers):
            if header:
                row_data[header] = values[index] if index < len(values) else None

        form_data = {
            field: _cell_text(row_data.get(field))
            for field in FORM_COLUMNS
        }
        row_form = AddMedicineForm(form_data)

        if not row_form.is_valid():
            details = []
            for field, field_errors in row_form.errors.items():
                label = field.replace("_", " ").title()
                details.append(f"{label}: {', '.join(str(error) for error in field_errors)}")
            errors.append(f"Row {row_number}: " + "; ".join(details))
            continue

        cleaned = row_form.cleaned_data
        key = (
            cleaned["name"].casefold(),
            cleaned["active_ingredient"].casefold(),
            cleaned["strength"].casefold(),
        )
        if key in seen:
            errors.append(
                f"Row {row_number}: this medicine appears more than once in the file."
            )
            continue

        seen.add(key)
        valid_rows.append(cleaned)

    if nonempty_count == 0:
        errors.append("The file does not contain any medicine rows.")

    if errors:
        raise BatchUploadError(errors[:20])

    return valid_rows


def parse_medicine_upload(uploaded_file):
    """Read and validate CSV or XLSX data without changing the database."""
    filename = (uploaded_file.name or "").lower()

    if filename.endswith(".csv"):
        try:
            contents = uploaded_file.read().decode("utf-8-sig")
            reader = csv.reader(io.StringIO(contents))
            headers = _normalise_headers(next(reader, None))
            return _validate_rows(headers, enumerate(reader, start=2))
        except (UnicodeDecodeError, csv.Error):
            raise BatchUploadError([
                "The CSV file could not be read. Save it as UTF-8 CSV and try again."
            ])

    if filename.endswith(".xlsx"):
        try:
            workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
        except (InvalidFileException, BadZipFile, OSError, ValueError):
            raise BatchUploadError([
                "The Excel file is invalid. Please upload a valid .xlsx file."
            ])

        try:
            worksheet = workbook.active
            row_iterator = worksheet.iter_rows(values_only=True)
            headers = _normalise_headers(next(row_iterator, None))
            return _validate_rows(headers, enumerate(row_iterator, start=2))
        finally:
            workbook.close()

    raise BatchUploadError(["Please upload a .csv or .xlsx file."])


def import_medicine_rows(pharmacy, user, rows):
    """
    Import validated rows atomically.

    Existing catalogue medicines are reused. If the pharmacy already lists a
    medicine, only its quantity and minimum threshold are updated; the shared
    medicine profile is not changed by this import.
    """
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for data in rows:
            medicine = Medicine.objects.filter(
                name__iexact=data["name"],
                active_ingredient__iexact=data["active_ingredient"],
                strength__iexact=data["strength"],
            ).first()

            if medicine is None:
                medicine = Medicine.objects.create(
                    name=data["name"],
                    active_ingredient=data["active_ingredient"],
                    category=data["category"],
                    strength=data["strength"],
                )

            inventory = (
                Inventory.objects.filter(pharmacy=pharmacy, medicine=medicine)
                .select_related("pharmacy", "medicine")
                .first()
            )

            if inventory is None:
                inventory = Inventory.objects.create(
                    pharmacy=pharmacy,
                    medicine=medicine,
                    quantity=data["quantity"],
                    minimum_threshold=data["minimum_threshold"],
                )
                record_inventory_change(
                    inventory,
                    user,
                    "create",
                    before_snapshot={},
                    after_snapshot=inventory_snapshot(inventory),
                )
                previous_was_low = False
                created_count += 1
            else:
                previous_was_low = (
                    inventory.quantity <= inventory.minimum_threshold
                )
                before_snapshot = inventory_snapshot(inventory)
                values_changed = (
                    inventory.quantity != data["quantity"]
                    or inventory.minimum_threshold != data["minimum_threshold"]
                )
                if values_changed:
                    inventory.quantity = data["quantity"]
                    inventory.minimum_threshold = data["minimum_threshold"]
                    inventory.save()
                    record_inventory_change(
                        inventory,
                        user,
                        "update",
                        before_snapshot=before_snapshot,
                        after_snapshot=inventory_snapshot(inventory),
                    )
                updated_count += 1

            update_low_stock_alert(
                inventory,
                user,
                previous_was_low=previous_was_low,
            )

    return {"created": created_count, "updated": updated_count}
