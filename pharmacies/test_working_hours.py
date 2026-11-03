from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .working_hours import is_open_at, parse_working_hours


class WorkingHoursTests(SimpleTestCase):
    sudan_timezone = timezone(timedelta(hours=2))

    def test_week_range_can_wrap_from_saturday_to_thursday(self):
        tuesday_morning = datetime(
            2026, 11, 3, 11, 0, tzinfo=self.sudan_timezone
        )

        self.assertTrue(
            is_open_at(
                "Sat-Thu 08:00-22:00; Fri 16:00-22:00",
                tuesday_morning,
            )
        )

    def test_closed_day_is_not_treated_as_open(self):
        friday_evening = datetime(
            2026, 11, 6, 18, 0, tzinfo=self.sudan_timezone
        )

        self.assertFalse(
            is_open_at(
                "Sat-Thu 08:00-22:00; Fri Closed",
                friday_evening,
            )
        )

    def test_overnight_hours_continue_after_midnight(self):
        saturday_early_morning = datetime(
            2026, 11, 7, 1, 0, tzinfo=self.sudan_timezone
        )

        self.assertTrue(
            is_open_at("Fri 20:00-02:00", saturday_early_morning)
        )

    def test_closing_time_is_not_included(self):
        tuesday_at_closing = datetime(
            2026, 11, 3, 22, 0, tzinfo=self.sudan_timezone
        )

        self.assertFalse(
            is_open_at("Tue 08:00-22:00", tuesday_at_closing)
        )

    def test_invalid_time_values_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_working_hours("Mon 25:00-26:00")
