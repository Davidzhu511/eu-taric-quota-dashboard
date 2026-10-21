"""Regression tests for the GitHub Actions CBAM research fallback."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ensure_cbam_research as m


class ResearchFallbackTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, 20, 30, tzinfo=timezone.utc)
        self.current = {
            "meta": {
                "data_date": "2026-10-21",
                "checked_at": "2026-10-21T19:35:00+00:00",
                "status": "ok",
                "errors": [],
            },
            "public_score": {"score": 27.9, "max_score": 70},
            "auction_analytics": {"stats": {"latest_price": 85.1}},
        }

    def research(self, status="scored", score=10.0, confidence="high", updated=None):
        return {
            "meta": {
                "updated_at": updated or "2026-10-21T20:00:00+00:00",
                "status": status,
                "confidence": confidence,
                "public_data_date": "2026-10-21",
            },
            "overlay_score": score,
        }

    def test_public_only_fallback_is_not_a_purchase_score(self):
        r = m.create_fallback(self.current, self.now)
        self.assertIsNone(r["overlay_score"])
        self.assertEqual(r["meta"]["status"], "public_only_fallback")
        self.assertEqual(r["meta"]["public_data_date"], "2026-10-21")
        self.assertIn("27.9/70", r["summary"])
        self.assertIn("€85.10/tCO₂", r["summary"])
        for key in ("headline", "summary", "bullets", "sources"):
            self.assertTrue(r[key])

    def test_preserve_verified_fresh_research(self):
        self.assertTrue(m.valid_same_day_research(self.research(), self.current, self.now))

    def test_do_not_preserve_outdated_or_incomplete_research(self):
        cases = [
            self.research(score=None),
            self.research(score=31),
            self.research(score=-1),
            self.research(status="partial_data"),
            self.research(confidence="low"),
            self.research(updated="2026-10-21T18:00:00+00:00"),
        ]
        mismatched = self.research()
        mismatched["meta"]["public_data_date"] = "2026-10-20"
        cases.append(mismatched)
        for value in cases:
            with self.subTest(value=value):
                self.assertFalse(m.valid_same_day_research(value, self.current, self.now))

    def test_degraded_public_data_keeps_overlay_null(self):
        self.current["meta"]["status"] = "degraded"
        self.current["meta"]["errors"] = ["market download unavailable"]
        r = m.create_fallback(self.current, self.now)
        self.assertIsNone(r["overlay_score"])
        self.assertIn("公共数据存在异常", r["meta"]["confidence"])


if __name__ == "__main__":
    unittest.main()
