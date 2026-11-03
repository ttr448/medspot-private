from django.test import SimpleTestCase

from .working_hours import parse_working_hours


class WorkingHoursTests(SimpleTestCase):
    def test_valid_week_schedule_is_parsed(self):
        schedule = parse_working_hours(
            "Sat-Thu 08:00-22:00; Fri Closed"
        )

        self.assertEqual(schedule[0], [(8 * 60, 22 * 60)])
        self.assertEqual(schedule[4], [])
        self.assertEqual(schedule[5], [(8 * 60, 22 * 60)])

    def test_invalid_time_values_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_working_hours("Mon 25:00-26:00")

    def test_invalid_day_format_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_working_hours("weekdays 08:00-22:00")
