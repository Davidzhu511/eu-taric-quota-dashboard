"""Pure checks for whether the daily quota scrape is complete and current."""
import argparse
import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UK_CODES = {"058604", "058605", "058606", "058607", "058608"}

def period_contains(period, day, jurisdiction):
    try:
        if jurisdiction == "EU":
            start, end = period.split(" - ")
            return datetime.strptime(start, "%d-%m-%Y").date() <= day <= datetime.strptime(end, "%d-%m-%Y").date()
        start, end = period.split(" — ")
        return date.fromisoformat(start) <= day <= date.fromisoformat(end)
    except (ValueError, AttributeError):
        return False

def is_complete(payload, day, jurisdiction):
    target = 55 if jurisdiction == "EU" else 5
    meta = payload.get("meta", {})
    items = payload.get("items", [])
    try:
        count_ok = (int(meta.get("total_count", -1)) == target
                    and int(meta.get("successful_count", -1)) == target
                    and int(meta.get("failed_count", -1)) == 0)
    except (ValueError, TypeError):
        return False
    codes = [str(item.get("code", "")) for item in items]
    if (not count_ok or len(items) != target or len(set(codes)) != target
            or (jurisdiction == "UK" and set(codes) != UK_CODES)
            or str(meta.get("checked_at", ""))[:10] != day.isoformat()):
        return False
    period = meta.get("validity_period", "")
    if not period_contains(period, day, jurisdiction):
        return False
    return all(item.get("validity_period") == period
               and not item.get("stale") and not item.get("error")
               for item in items)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--complete-on", required=True, help="Europe/Berlin YYYY-MM-DD")
    args = parser.parse_args()
    day = date.fromisoformat(args.complete_on)
    try:
        eu = json.loads((ROOT / "data/current.json").read_text(encoding="utf-8"))
        uk = json.loads((ROOT / "data/uk/current.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"no valid snapshots: {exc}")
        raise SystemExit(1)
    eu_ok = is_complete(eu, day, "EU")
    uk_ok = is_complete(uk, day, "UK")
    print(f"complete-on {day}: EU={eu_ok}, UK={uk_ok}")
    raise SystemExit(0 if eu_ok and uk_ok else 1)

if __name__ == "__main__":
    main()
