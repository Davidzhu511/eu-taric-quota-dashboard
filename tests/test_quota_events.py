import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_quota_events import build, policy_for

PERIOD = "01-10-2026 - 31-12-2026"
NEXT_PERIOD = "01-01-2027 - 31-03-2027"
POLICY = [{"from": "2026-07-01", "through": "2026-12-31", "sources": [{"name": "EU act", "url": "https://eur-lex.europa.eu"}]}]


def payload(balance, *, hour=10, pressure=0.2, day="21", **fields):
    row = dict(code="099600", category="1A", origin="Other countries", validity_period=PERIOD,
               balance_kg=balance, initial_amount_kg=10_000_000, awaiting_to_balance_ratio=pressure)
    row.update(fields)
    return dict(meta=dict(checked_at=f"2026-11-{day}T{hour:02}:00:00+01:00",
                          official_update_date=f"2026-11-{day}", validity_period=row["validity_period"],
                          next_period=NEXT_PERIOD), items=[row])


class QuotaEventsTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.data, self.previous = (Path(folder.name) / name for name in ("now", "before"))
        for path in (self.data, self.previous):
            (path / "uk").mkdir(parents=True)
            (path / "uk/current.json").write_text("{}")
            (path / "quarterly-summary.json").write_text("{}")

    def build_events(self, before, after):
        (self.previous / "current.json").write_text(json.dumps(before))
        (self.data / "current.json").write_text(json.dumps(after))
        return build(self.data, self.previous, POLICY)

    def test_policy_window_requires_the_entire_quarter(self):
        self.assertEqual(policy_for(PERIOD, POLICY)["status"], "distribution_rules_verified")
        self.assertEqual(policy_for(NEXT_PERIOD, POLICY)["status"], "distribution_rules_unverified")

    def test_same_official_day_new_pressure_is_retained_and_deduplicated(self):
        before, after = payload(5_000_000), payload(5_000_000, hour=15, pressure=0.95)
        first = self.build_events(before, after)
        event = next(x for x in first["events"] if x["kind"] == "pending_pressure_increased")
        self.assertEqual(event["after"]["checked_at"], "2026-11-21T15:00:00+01:00")
        (self.data / "quota-events.json").write_text(json.dumps(first))
        second = self.build_events(before, payload(5_000_000, hour=16, pressure=0.95))
        self.assertEqual([x["id"] for x in second["events"] if x["kind"] == event["kind"]], [event["id"]])
        third = self.build_events(after, after)
        self.assertIn(event, third["events"])

    def test_unknown_and_cross_quarter_balances_do_not_create_exhaustion(self):
        before = payload(100_000)
        for after in (payload(0, stale=True), payload(None), payload(0, validity_period=NEXT_PERIOD)):
            with self.subTest(after=after):
                changes = {event["kind"] for event in self.build_events(before, after)["events"]}
                self.assertNotIn("newly_exhausted", changes)
        self.assertIn("period_opened", changes)
