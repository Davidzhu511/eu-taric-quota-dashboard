"""Regression checks for the handover between quota quarters."""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from update_dashboard import calculate_quota_metrics, search_detail_url
from update_uk_dashboard import normalise_header, row_to_item, select_active, select_next


class FakeResponse:
    def __init__(self, url, html):
        self.url, self.text, self.apparent_encoding = url, html, "utf-8"
        self.encoding = "utf-8"

    def raise_for_status(self):
        pass


class FakeSession:
    def get(self, url, params=None, timeout=None):
        rows = "".join(
            f'<tr><td>099605</td><td>{start}</td><td>{end}</td>'
            f'<td><a href="quota_tariff_details.jsp?Lang=en&amp;Code=099605&amp;StartDate={start}">Details</a></td></tr>'
            for start, end in (("01-07-2026", "30-09-2026"), ("01-10-2026", "31-12-2026"))
        )
        return FakeResponse(url, f"<html><body>Last tariff QUOTA update: 28-09-2026<table>{rows}</table></body></html>")


class QuarterTransitionTests(unittest.TestCase):
    def test_eu_keeps_current_and_exposes_next_quarter(self):
        current, updated, future_flag, next_url = search_detail_url(FakeSession(), "099605", date(2026, 9, 29))
        self.assertIn("StartDate=01-07-2026", current)
        self.assertIn("StartDate=01-10-2026", next_url)
        self.assertEqual(updated, "2026-09-28")
        self.assertFalse(future_flag)

    def test_eu_awaiting_pressure_compares_pending_requests_with_balance(self):
        metrics = calculate_quota_metrics(initial=1000, balance=100, awaiting=80)
        self.assertAlmostEqual(metrics["awaiting_ratio"], 0.08)
        self.assertAlmostEqual(metrics["awaiting_to_balance_ratio"], 0.8)
        self.assertEqual(metrics["effective_buffer_kg"], 20)

        oversubscribed = calculate_quota_metrics(initial=1000, balance=100, awaiting=150)
        self.assertAlmostEqual(oversubscribed["awaiting_to_balance_ratio"], 1.5)
        self.assertEqual(oversubscribed["effective_buffer_kg"], 0)
        self.assertAlmostEqual(oversubscribed["outside_ratio"], 1 / 3)

    def test_uk_future_balance_is_unknown_and_past_period_is_rejected(self):
        rows = [dict(quota_order_number="058608", quota_definition_validity_start_date=start,
                     quota_definition_validity_end_date=end, quota_definition_initial_volume="25029000",
                     quota_definition_balance=balance, quota_definition_status=status)
                for start, end, balance, status in (("2026-07-01", "2026-09-30", "730790.794", "Open"),
                                                     ("2026-10-01", "2026-12-31", "#NA", "Future"))]
        future = select_next(rows, "058608", date(2026, 9, 29))
        self.assertEqual(future, rows[1])
        item = row_to_item(future, "058608", "Residual", "其他国家", True, "https://example.org/data.csv")
        self.assertIsNone(item["balance"])
        self.assertIsNone(item["used_percentage"])
        self.assertEqual(select_active(rows, "058608", date(2026, 10, 1)), rows[1])
        with self.assertRaises(RuntimeError):
            select_active(rows, "058608", date(2027, 1, 1))


if __name__ == "__main__":
    unittest.main()
