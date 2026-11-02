"""Freshness gate must reject plausible-looking but partial/old snapshots."""
import copy
import unittest
from datetime import date
from scripts.dashboard_health import is_complete

DAY = date(2026, 11, 2)
EU_PERIOD = "01-10-2026 - 31-12-2026"
UK_PERIOD = "2026-10-01 — 2026-12-31"

def fixture(jurisdiction):
    eu = jurisdiction == "EU"
    count = 55 if eu else 5
    period = EU_PERIOD if eu else UK_PERIOD
    codes = [f"{99000+i:06d}" for i in range(count)] if eu else [f"{58604+i:06d}" for i in range(count)]
    return {
        "meta": {"checked_at": "2026-11-02T07:50:00+01:00",
                 "total_count": count, "successful_count": count,
                 "failed_count": 0, "validity_period": period,
                 "official_update_date": "2026-10-30"},
        "items": [{"code": code, "validity_period": period, "stale": False, "error": ""} for code in codes],
    }

class DailyCompletenessTests(unittest.TestCase):
    def test_both_full(self):
        self.assertTrue(is_complete(fixture("EU"), DAY, "EU"))
        self.assertTrue(is_complete(fixture("UK"), DAY, "UK"))
    def test_older_official_date_not_automatically_failure(self):
        x = fixture("EU")
        x["meta"]["official_update_date"] = "2026-10-23"
        self.assertTrue(is_complete(x, DAY, "EU"))
    def test_metadata_count_not_sufficient(self):
        x = fixture("EU")
        x["items"].pop()
        self.assertFalse(is_complete(x, DAY, "EU"))
    def test_duplicate_code_rejected(self):
        x = fixture("EU")
        x["items"][1]["code"] = x["items"][0]["code"]
        self.assertFalse(is_complete(x, DAY, "EU"))
    def test_stale_and_error_rejected(self):
        x = fixture("EU")
        x["items"][0]["stale"] = True
        self.assertFalse(is_complete(x, DAY, "EU"))
        x = fixture("UK")
        x["items"][0]["error"] = "timeout"
        self.assertFalse(is_complete(x, DAY, "UK"))
    def test_wrong_quarter_and_day_rejected(self):
        x = fixture("UK")
        x["meta"]["validity_period"] = "2026-07-01 — 2026-09-30"
        self.assertFalse(is_complete(x, DAY, "UK"))
        x = fixture("EU")
        x["meta"]["checked_at"] = "2026-11-01T07:50:00+01:00"
        self.assertFalse(is_complete(x, DAY, "EU"))
    def test_partial_metadata_rejected(self):
        x = fixture("EU")
        x["meta"]["successful_count"] = 54
        x["meta"]["failed_count"] = 1
        self.assertFalse(is_complete(x, DAY, "EU"))

if __name__ == "__main__":
    unittest.main()
