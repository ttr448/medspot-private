from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy


User = get_user_model()


class PatientMedicineSearchTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username="patient1",
            password="test-password-123",
            role="patient",
            is_active=True,
        )
        self.verified_pharmacist = User.objects.create_user(
            username="pharmacist1",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.pharmacy = Pharmacy.objects.create(
            name="ABC Pharmacy",
            address="123 Main Street",
            owner=self.verified_pharmacist,
        )
        self.panadol = Medicine.objects.create(
            name="Panadol",
            active_ingredient="Paracetamol",
            category="Analgesic",
            dosage_form="Tablet",
        )
        self.available_item = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.panadol,
            quantity=25,
        )
        self.search_url = reverse("users:patient_search")
        self.client.force_login(self.patient)

    def test_patient_can_search_by_medicine_name_case_insensitively(self):
        response = self.client.get(self.search_url, {"q": "pAnAdOl"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panadol")
        self.assertContains(response, "ABC Pharmacy")
        self.assertContains(response, "123 Main Street")
        self.assertContains(response, "25")
        self.assertEqual(list(response.context["results"]), [self.available_item])

    def test_patient_can_search_by_active_ingredient(self):
        response = self.client.get(self.search_url, {"q": "paracetamol"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panadol")
        self.assertEqual(list(response.context["results"]), [self.available_item])

    def test_medicine_with_zero_quantity_is_not_shown_as_available(self):
        self.available_item.quantity = 0
        self.available_item.save(update_fields=["quantity"])

        response = self.client.get(self.search_url, {"q": "Panadol"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pharmacies found with this medicine.")
        self.assertFalse(response.context["results"].exists())

    def test_unverified_pharmacy_is_not_in_search_results(self):
        unverified_user = User.objects.create_user(
            username="pending_pharmacist",
            password="test-password-123",
            role="pharmacist",
            is_active=False,
            is_verified=False,
        )
        pending_pharmacy = Pharmacy.objects.create(
            name="Pending Pharmacy",
            address="9 Side Street",
            owner=unverified_user,
        )
        Inventory.objects.create(
            pharmacy=pending_pharmacy,
            medicine=self.panadol,
            quantity=10,
        )

        response = self.client.get(self.search_url, {"q": "Panadol"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ABC Pharmacy")
        self.assertNotContains(response, "Pending Pharmacy")

    def test_empty_search_does_not_show_all_inventory(self):
        response = self.client.get(self.search_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a medicine name or active ingredient")
        self.assertNotContains(response, "ABC Pharmacy")
        self.assertFalse(response.context["results"].exists())

    def test_unauthenticated_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(self.search_url)

        self.assertRedirects(response, reverse("users:login"))

    def test_non_patient_cannot_access_patient_search(self):
        pharmacist = User.objects.create_user(
            username="pharmacist2",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(pharmacist)

        response = self.client.get(self.search_url)

        self.assertRedirects(response, reverse("users:login"))
