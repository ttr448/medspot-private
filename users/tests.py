from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

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
            strength="500 mg",
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
        self.assertContains(response, "500 mg")
        self.assertEqual(list(response.context["results"]), [self.available_item])

    def test_patient_can_filter_search_by_medicine_strength(self):
        another_medicine = Medicine.objects.create(
            name="Panadol",
            active_ingredient="Paracetamol",
            category="Analgesic",
            strength="250 mg",
        )
        Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=another_medicine,
            quantity=8,
        )

        response = self.client.get(
            self.search_url,
            {"q": "Panadol", "strength": "500 mg"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["results"]), [self.available_item])
        self.assertContains(response, "500 mg")
        self.assertNotContains(response, "250 mg")

    def test_working_hours_are_displayed_only_when_requested(self):
        self.pharmacy.working_hours = "Sat-Thu 08:00-22:00"
        self.pharmacy.save(update_fields=["working_hours"])

        default_response = self.client.get(self.search_url, {"q": "Panadol"})
        self.assertEqual(default_response.status_code, 200)
        self.assertNotContains(default_response, "Sat-Thu 08:00-22:00")

        hours_response = self.client.get(
            self.search_url,
            {"q": "Panadol", "show_hours": "1"},
        )
        self.assertEqual(hours_response.status_code, 200)
        self.assertTrue(hours_response.context["show_hours"])
        self.assertContains(hours_response, "Sat-Thu 08:00-22:00")

    @patch("users.views.timezone.now")
    def test_open_now_filter_returns_only_pharmacies_open_in_sudan_time(self, mocked_now):
        # 09:00 UTC is 11:00 in Khartoum.
        mocked_now.return_value = datetime(
            2026, 11, 3, 9, 0, tzinfo=ZoneInfo("UTC")
        )
        self.pharmacy.working_hours = "Sat-Thu 08:00-22:00; Fri 16:00-22:00"
        self.pharmacy.save(update_fields=["working_hours"])

        closed_user = User.objects.create_user(
            username="closed_pharmacist",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        closed_pharmacy = Pharmacy.objects.create(
            name="Closed Pharmacy",
            address="456 Side Street",
            owner=closed_user,
            working_hours="Mon-Sun 18:00-23:00",
        )
        Inventory.objects.create(
            pharmacy=closed_pharmacy,
            medicine=self.panadol,
            quantity=10,
        )

        response = self.client.get(
            self.search_url,
            {"q": "Panadol", "open_now": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["open_now"])
        self.assertEqual(
            [item.pharmacy.name for item in response.context["results"]],
            ["ABC Pharmacy"],
        )
        self.assertContains(response, "Only show pharmacies open now")

    @patch("users.views.timezone.now")
    def test_open_now_filter_excludes_pharmacies_without_valid_hours(self, mocked_now):
        mocked_now.return_value = datetime(
            2026, 11, 3, 9, 0, tzinfo=ZoneInfo("UTC")
        )
        self.pharmacy.working_hours = ""
        self.pharmacy.save(update_fields=["working_hours"])

        response = self.client.get(
            self.search_url,
            {"q": "Panadol", "open_now": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["results"]), [])
        self.assertContains(response, "No pharmacies with this medicine are currently marked as open.")

    def test_autocomplete_returns_available_medicine_suggestions(self):
        response = self.client.get(
            reverse("users:medicine_suggestions"),
            {"q": "pana"},
        )

        self.assertEqual(response.status_code, 200)
        suggestions = response.json()["suggestions"]
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["name"], "Panadol")
        self.assertEqual(suggestions[0]["strength"], "500 mg")

    def test_autocomplete_ignores_queries_shorter_than_two_characters(self):
        response = self.client.get(
            reverse("users:medicine_suggestions"),
            {"q": "p"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggestions"], [])

    def test_autocomplete_is_not_available_to_non_patients(self):
        pharmacist = User.objects.create_user(
            username="suggestion_pharmacist",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(pharmacist)

        response = self.client.get(
            reverse("users:medicine_suggestions"),
            {"q": "pana"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["suggestions"], [])

    def test_location_permission_is_requested_automatically(self):
        response = self.client.get(self.search_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "requestLocation().then(function (coordinates)")
        self.assertNotContains(response, "Find Nearest Pharmacy")

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

    def test_results_are_sorted_by_haversine_distance(self):
        self.pharmacy.latitude = "12.000000"
        self.pharmacy.longitude = "15.000000"
        self.pharmacy.save(update_fields=["latitude", "longitude"])

        closer_pharmacist = User.objects.create_user(
            username="closer_pharmacist",
            password="test-password-123",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        closer_pharmacy = Pharmacy.objects.create(
            name="Closer Pharmacy",
            address="Near the patient",
            latitude="12.010000",
            longitude="15.000000",
            owner=closer_pharmacist,
        )
        closer_item = Inventory.objects.create(
            pharmacy=closer_pharmacy,
            medicine=self.panadol,
            quantity=12,
        )

        response = self.client.post(
            self.search_url,
            {"q": "Panadol", "lat": "12.009000", "lng": "15.000000"},
        )

        self.assertEqual(response.status_code, 200)
        results = response.context["results"]
        self.assertEqual(results[0], closer_item)
        self.assertLess(results[0].distance_km, results[1].distance_km)
        self.assertContains(response, "Nearest pharmacy: <strong>Closer Pharmacy</strong>")

    def test_invalid_patient_coordinates_are_ignored_safely(self):
        response = self.client.post(
            self.search_url,
            {"q": "Panadol", "lat": "95", "lng": "200"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["location_error"])
        self.assertFalse(response.context["has_patient_location"])
        self.assertEqual(list(response.context["results"]), [self.available_item])



from decimal import Decimal

from django.contrib.messages import get_messages


class PatientRegistrationTests(TestCase):
    def test_patient_can_register_successfully(self):
        response = self.client.post(
            reverse("users:register_patient"),
            {
                "username": "new_patient",
                "email": "patient@example.com",
                "first_name": "New",
                "last_name": "Patient",
                "password1": "Very-Strong!Password-2026#",
                "password2": "Very-Strong!Password-2026#",
            },
        )

        self.assertRedirects(response, reverse("users:login"))
        user = User.objects.get(username="new_patient")
        self.assertEqual(user.role, "patient")
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_verified)

    def test_patient_registration_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("users:register_patient"),
            {
                "username": "invalid_patient",
                "email": "invalid@example.com",
                "password1": "Very-Strong!Password-2026#",
                "password2": "Different-Strong!Password-2026#",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="invalid_patient").exists())


class PharmacistRegistrationAndLoginTests(TestCase):
    def test_new_pharmacist_is_registered_pending_admin_approval(self):
        response = self.client.post(
            reverse("users:register_pharmacist"),
            {
                "username": "new_pharmacist",
                "email": "pharmacist@example.com",
                "first_name": "New",
                "last_name": "Pharmacist",
                "password1": "Very-Strong!Password-2026#",
                "password2": "Very-Strong!Password-2026#",
                "pharmacy_name": "New Pharmacy",
                "pharmacy_address": "10 Main Street",
                "latitude": "15.500000",
                "longitude": "32.500000",
            },
        )

        self.assertRedirects(response, reverse("users:login"))
        pharmacist = User.objects.get(username="new_pharmacist")
        self.assertEqual(pharmacist.role, "pharmacist")
        self.assertFalse(pharmacist.is_active)
        self.assertFalse(pharmacist.is_verified)

        pharmacy = Pharmacy.objects.get(owner=pharmacist)
        self.assertEqual(pharmacy.name, "New Pharmacy")
        self.assertEqual(pharmacy.latitude, Decimal("15.500000"))
        self.assertEqual(pharmacy.longitude, Decimal("32.500000"))

    def test_pending_pharmacist_cannot_log_in(self):
        pharmacist = User.objects.create_user(
            username="pending_pharmacist",
            password="Very-Strong!Password-2026#",
            role="pharmacist",
            is_active=False,
            is_verified=False,
        )

        response = self.client.post(
            reverse("users:login"),
            {
                "username": pharmacist.username,
                "password": "Very-Strong!Password-2026#",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pending admin approval")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_patient_login_redirects_to_patient_search(self):
        patient = User.objects.create_user(
            username="login_patient",
            password="Very-Strong!Password-2026#",
            role="patient",
            is_active=True,
            is_verified=True,
        )

        response = self.client.post(
            reverse("users:login"),
            {
                "username": patient.username,
                "password": "Very-Strong!Password-2026#",
            },
        )

        self.assertRedirects(response, reverse("users:patient_search"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), patient.pk)

    def test_verified_pharmacist_login_redirects_to_dashboard(self):
        pharmacist = User.objects.create_user(
            username="approved_pharmacist",
            password="Very-Strong!Password-2026#",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        Pharmacy.objects.create(
            name="Approved Pharmacy",
            address="20 Market Street",
            owner=pharmacist,
        )

        response = self.client.post(
            reverse("users:login"),
            {
                "username": pharmacist.username,
                "password": "Very-Strong!Password-2026#",
            },
        )

        self.assertRedirects(response, reverse("pharmacies:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), pharmacist.pk)

    def test_logout_ends_the_authenticated_session(self):
        patient = User.objects.create_user(
            username="logout_patient",
            password="Very-Strong!Password-2026#",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        self.client.force_login(patient)

        response = self.client.get(reverse("users:logout"))

        self.assertRedirects(response, reverse("users:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PatientSearchLocationEdgeCaseTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username="location_patient",
            password="Very-Strong!Password-2026#",
            role="patient",
            is_active=True,
            is_verified=True,
        )
        self.pharmacist = User.objects.create_user(
            username="coordinate_pharmacist",
            password="Very-Strong!Password-2026#",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        self.pharmacy = Pharmacy.objects.create(
            name="No Coordinates Pharmacy",
            address="Unknown location",
            owner=self.pharmacist,
        )
        self.medicine = Medicine.objects.create(
            name="Location Test Medicine",
            active_ingredient="Test Ingredient",
        )
        self.inventory = Inventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.medicine,
            quantity=7,
        )
        self.client.force_login(self.patient)
        self.search_url = reverse("users:patient_search")

    def test_pharmacy_without_coordinates_is_not_assigned_a_distance(self):
        response = self.client.post(
            self.search_url,
            {"q": "Location Test Medicine", "lat": "15.5", "lng": "32.5"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["nearest_pharmacy"])
        self.assertEqual(response.context["map_locations"], [])
        self.assertIsNone(response.context["results"][0].distance_km)
        self.assertContains(response, "No pharmacy coordinates are available yet")

    def test_nearest_valid_pharmacy_is_selected_when_another_has_no_coordinates(self):
        closer_user = User.objects.create_user(
            username="valid_coordinate_pharmacist",
            password="Very-Strong!Password-2026#",
            role="pharmacist",
            is_active=True,
            is_verified=True,
        )
        closer_pharmacy = Pharmacy.objects.create(
            name="Valid Coordinates Pharmacy",
            address="Known location",
            latitude="15.501000",
            longitude="32.501000",
            owner=closer_user,
        )
        closer_inventory = Inventory.objects.create(
            pharmacy=closer_pharmacy,
            medicine=self.medicine,
            quantity=4,
        )

        response = self.client.post(
            self.search_url,
            {"q": "Location Test Medicine", "lat": "15.500000", "lng": "32.500000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["nearest_pharmacy"], closer_inventory)
        self.assertEqual(response.context["results"][0], closer_inventory)
        self.assertIsNone(response.context["results"][1].distance_km)

    def test_only_one_coordinate_is_treated_as_invalid_location(self):
        response = self.client.post(
            self.search_url,
            {"q": "Location Test Medicine", "lat": "15.5"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["location_error"])
        self.assertFalse(response.context["has_patient_location"])
        self.assertContains(response, "We could not read a valid location")
