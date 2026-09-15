from datetime import date
from unittest import TestCase

from app.services.filters import available_period_overlap, rolling_period_start


class RollingPeriodTests(TestCase):
    def test_calendar_month_boundaries_and_leap_years(self) -> None:
        self.assertEqual(rolling_period_start(date(2026, 6, 30), 1), date(2026, 5, 31))
        self.assertEqual(rolling_period_start(date(2024, 3, 31), 1), date(2024, 3, 1))
        self.assertEqual(rolling_period_start(date(2024, 2, 29), 12), date(2023, 3, 1))
        self.assertEqual(rolling_period_start(date(2026, 8, 22), 6), date(2026, 2, 23))

    def test_available_scoring_overlap_can_be_empty(self) -> None:
        coverage_start = date(2026, 5, 25)
        coverage_end = date(2026, 8, 21)
        self.assertEqual(
            available_period_overlap(
                date(2026, 2, 22), coverage_end, coverage_start, coverage_end
            ),
            (coverage_start, coverage_end),
        )
        self.assertEqual(
            available_period_overlap(
                date(2025, 1, 1), date(2025, 1, 7), coverage_start, coverage_end
            ),
            (None, None),
        )
