import unittest

from scripts.update_dashboard import should_preserve_previous_snapshot


class SnapshotQualityTests(unittest.TestCase):
    def setUp(self):
        self.complete = {
            "official_update_date": "2026-10-26",
            "validity_period": "01-10-2026 - 31-12-2026",
            "successful_count": 55,
            "failed_count": 0,
            "total_count": 55,
        }

    def test_preserves_more_complete_snapshot_for_same_scope(self):
        candidate = dict(self.complete, successful_count=33, failed_count=22)
        self.assertTrue(should_preserve_previous_snapshot(self.complete, candidate))

    def test_allows_new_official_date_even_when_partial(self):
        candidate = dict(
            self.complete,
            official_update_date="2026-10-27",
            successful_count=33,
            failed_count=22,
        )
        self.assertFalse(should_preserve_previous_snapshot(self.complete, candidate))

    def test_allows_equal_or_better_quality(self):
        self.assertFalse(should_preserve_previous_snapshot(self.complete, self.complete))
        candidate = dict(self.complete, successful_count=55, failed_count=0)
        self.assertFalse(should_preserve_previous_snapshot(self.complete, candidate))

    def test_requires_matching_validity_period_and_population(self):
        different_period = dict(
            self.complete,
            validity_period="01-01-2027 - 31-03-2027",
            successful_count=33,
            failed_count=22,
        )
        different_population = dict(
            self.complete,
            successful_count=33,
            failed_count=22,
            total_count=56,
        )
        self.assertFalse(should_preserve_previous_snapshot(self.complete, different_period))
        self.assertFalse(should_preserve_previous_snapshot(self.complete, different_population))


if __name__ == "__main__":
    unittest.main()
