"""Recovery guard must not spam GitHub or mistake a gate-only success for data."""

import unittest
from datetime import datetime, timezone

from scripts.quota_retry_guard import retry_blocker

NOW = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)


class QuotaRetryGuardTests(unittest.TestCase):
    def test_missing_data_can_trigger_recovery(self):
        self.assertIsNone(retry_blocker([], NOW))
        self.assertIsNone(retry_blocker([
            {"status": "completed", "conclusion": "success",
             "createdAt": "2026-11-07T12:00:00Z"}
        ], NOW))  # A gate-only success might have skipped the actual update.

    def test_prevents_dispatch_when_another_run_is_active(self):
        message = retry_blocker([
            {"status": "in_progress", "conclusion": None,
             "createdAt": "2026-11-07T14:30:00Z"}
        ], NOW)
        self.assertIn("already active", message)

    def test_caps_three_failed_attempts_in_berlin_day(self):
        runs = [
            {"status": "completed", "conclusion": "failure",
             "createdAt": "2026-11-07T00:30:00Z"},
            {"status": "completed", "conclusion": "failure",
             "createdAt": "2026-11-07T08:30:00Z"},
            {"status": "completed", "conclusion": "timed_out",
             "createdAt": "2026-11-07T12:30:00Z"},
        ]
        self.assertIn("retry cap 3", retry_blocker(runs, NOW))
        self.assertIsNone(retry_blocker(runs[:2], NOW))

    def test_berlin_midnight_not_utc_midnight(self):
        runs = [
            {"status": "completed", "conclusion": "failure",
             "createdAt": "2026-11-06T23:30:00Z"},
            {"status": "completed", "conclusion": "failure",
             "createdAt": "2026-11-07T08:30:00Z"},
            {"status": "completed", "conclusion": "failure",
             "createdAt": "2026-11-07T12:30:00Z"},
        ]
        self.assertIn("retry cap 3", retry_blocker(runs, NOW))
        runs[0]["createdAt"] = "2026-11-06T21:30:00Z"
        self.assertIsNone(retry_blocker(runs, NOW))

    def test_ignores_invalid_run_timestamps(self):
        self.assertIsNone(retry_blocker([
            {"status": "completed", "conclusion": "failure", "createdAt": "bad"}
        ], NOW))

    def test_rejects_naive_current_time(self):
        with self.assertRaises(ValueError):
            retry_blocker([], datetime(2026, 11, 7, 15, 0))


if __name__ == "__main__":
    unittest.main()
