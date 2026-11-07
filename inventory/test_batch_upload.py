import csv
from io import BytesIO, StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from alerts.models import Alert
from inventory.models import Inventory, InventoryLog
from medicines.models import Medicine
from pharmacies.models import Pharmacy


User = get_user_model()


class BatchMedicineUploadTests(TestCase):
    def setUp(self):
        self.pharmacist = User.objects.create_user(
            username="batch_pharmacist",
            password="Strong-Test-Password-2026!",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.pharmacy = Pharmacy.objects.create(
            name="Batch Pharmacy",
            address="123 Main Street",
            owner=self.pharmacist,
        )
        self.panadol = Medicine.objects.create(
            name="Panadol",
            active_ingredient="Paracetamol",
            category="Analgesic",
            strength="500 mg",
        )
        self.existing_inventory = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.panadol,
            quantity=20,
            minimum_threshold=5,
        )
        self.client.force_login(self.pharmacist)

    def upload_csv(self, content):
        return SimpleUploadedFile(
            "medicines.csv",
            content.encode("utf-8"),
            content_type="text/csv",
        )

    def test_csv_upload_adds_new_medicine_updates_existing_stock_and_creates_alert(self):
        content = (
            "name,active_ingredient,category,strength,quantity,minimum_threshold\n"
            "Panadol,Paracetamol,Analgesic,500 mg,4,5\n"
            "Amoxicillin,Amoxicillin,Antibiotic,250 mg,12,3\n"
        )
        response = self.client.post(
            reverse("inventory:medicine_batch_upload"),
            {"file": self.upload_csv(content)},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.existing_inventory.refresh_from_db()
        self.assertEqual(self.existing_inventory.quantity, 4)
        self.assertEqual(self.existing_inventory.minimum_threshold, 5)

        new_inventory = Inventory.objects.get(
            pharmacy=self.pharmacy,
            medicine__name="Amoxicillin",
        )
        self.assertEqual(new_inventory.quantity, 12)
        self.assertEqual(new_inventory.minimum_threshold, 3)

        self.assertTrue(
            Alert.objects.filter(
                pharmacy=self.pharmacy,
                medicine=self.panadol,
                alert_type="low_stock",
                acknowledged=False,
            ).exists()
        )
        self.assertEqual(InventoryLog.objects.count(), 2)

    def test_xlsx_upload_is_supported(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append([
            "name", "active_ingredient", "category",
            "strength", "quantity", "minimum_threshold",
        ])
        worksheet.append([
            "Ibuprofen", "Ibuprofen", "Pain relief",
            "200 mg", 15, 4,
        ])
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()

        uploaded_file = SimpleUploadedFile(
            "medicines.xlsx",
            buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response = self.client.post(
            reverse("inventory:medicine_batch_upload"),
            {"file": uploaded_file},
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        imported = Inventory.objects.get(
            pharmacy=self.pharmacy,
            medicine__name="Ibuprofen",
        )
        self.assertEqual(imported.quantity, 15)

    def test_invalid_row_prevents_the_entire_file_from_being_imported(self):
        content = (
            "name,active_ingredient,category,strength,quantity,minimum_threshold\n"
            "New Medicine,Ingredient,General,100 mg,10,2\n"
            "Bad Medicine,Ingredient,General,100 mg,-1,2\n"
        )
        response = self.client.post(
            reverse("inventory:medicine_batch_upload"),
            {"file": self.upload_csv(content)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Row 3")
        self.assertFalse(
            Inventory.objects.filter(
                pharmacy=self.pharmacy,
                medicine__name="New Medicine",
            ).exists()
        )
        self.existing_inventory.refresh_from_db()
        self.assertEqual(self.existing_inventory.quantity, 20)

    def test_duplicate_medicine_rows_are_rejected(self):
        content = (
            "name,active_ingredient,category,strength,quantity,minimum_threshold\n"
            "New Medicine,Ingredient,General,100 mg,10,2\n"
            "New Medicine,Ingredient,General,100 mg,8,2\n"
        )
        response = self.client.post(
            reverse("inventory:medicine_batch_upload"),
            {"file": self.upload_csv(content)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "appears more than once")
        self.assertFalse(
            Inventory.objects.filter(
                pharmacy=self.pharmacy,
                medicine__name="New Medicine",
            ).exists()
        )

    def test_patient_cannot_upload_medicines(self):
        patient = User.objects.create_user(
            username="batch_patient",
            password="Strong-Test-Password-2026!",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(patient)

        response = self.client.get(reverse("inventory:medicine_batch_upload"))

        self.assertRedirects(
            response,
            reverse("users:access_denied"),
            target_status_code=403,
        )

    def test_upload_page_displays_expected_columns(self):
        response = self.client.get(reverse("inventory:medicine_batch_upload"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "active_ingredient")
        self.assertContains(response, "minimum_threshold")
