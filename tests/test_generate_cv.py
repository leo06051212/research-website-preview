from datetime import date, datetime, timezone
import unittest

from scripts.generate_cv import default_generated_on


class GenerateCvTests(unittest.TestCase):
    def test_default_generation_date_uses_auckland_calendar_day(self):
        utc_instant = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)

        self.assertEqual(default_generated_on(utc_instant), date(2026, 7, 17))


if __name__ == "__main__":
    unittest.main()
