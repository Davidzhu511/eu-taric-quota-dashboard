---
name: quota-data-validation
description: Validate EU and UK tariff quota snapshots and quarterly allocation evidence without guessing missing values.
---

# EU/UK data validation

Start from the latest main `data/current.json`, `data/uk/current.json`, `data/quarterly-summary.json` and the source workflow run. Validate exact scope: 55 EU records and five UK Category 4 records (058604–058608), unique IDs, source fields, current period, success/fail counts, and stale flags.

Distinguish the Berlin fetch timestamp `checked_at` from the official upstream publication date `official_update_date`. Do not assert a scrape failure simply because a primary source has not updated over a weekend.

EU `Total awaiting allocation` describes requests awaiting assignment, not confirmed consumption. Recent allocated percentage applies to that official batch, never automatically to the whole quarter. Weighted historical allocation requires correct quarter, target pool, origin, opening import date, exhaustion, positive ratio and consistent historical evidence.

UK `#NA` is unknown; fill rate and volume changes cannot infer same-day quota allocation percentage. Leave UK weighted duty uncalculated if unavailable.

For any disagreement, report PASS/DEGRADED/FAIL with concrete code, historical source and business impact; never silently write guessed data. Run `python -m unittest discover -s tests -v` on code changes.
