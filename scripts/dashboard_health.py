"""Pure checks for whether the daily quota scrape is complete and current."""
import argparse
import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from urllib.error import URLError
from zoneinfo import ZoneInfo

from scripts.verify_live_site import DEFAULT_URL, fetch_bytes, make_url

ROOT = Path(__file__).resolve().parents[1]
UK_CODES = {"058604", "058605", "058606", "058607", "058608"}
BERLIN = ZoneInfo("Europe/Berlin")
SNAPSHOTS = {"EU": "data/current.json", "UK": "data/uk/current.json"}
PUBLICATION_FILES = (*SNAPSHOTS.values(), "data/quarterly-summary.json", "data/quota-events.json", "data/quota-policy.json")

def period_contains(period, day, jurisdiction):
    try:
        if jurisdiction == "EU":
            start, end = period.split(" - ")
            return datetime.strptime(start, "%d-%m-%Y").date() <= day <= datetime.strptime(end, "%d-%m-%Y").date()
        start, end = period.split(" — ")
        return date.fromisoformat(start) <= day <= date.fromisoformat(end)
    except (ValueError, AttributeError):
        return False

def is_complete(payload, day, jurisdiction, *, since=None):
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
    if since is not None:
        try:
            checked = datetime.fromisoformat(meta["checked_at"])
        except (TypeError, ValueError, KeyError):
            return False
        if checked.tzinfo is None or checked < since:
            return False
    period = meta.get("validity_period", "")
    if not period_contains(period, day, jurisdiction):
        return False
    return all(item.get("validity_period") == period
               and not item.get("stale") and not item.get("error")
               for item in items)

def latest_slot(now):
    """Use Berlin time and the latest due window even when a runner queues late."""
    berlin = now.astimezone(BERLIN)
    day = berlin.date()
    quarter_month = day.month in (1, 4, 7, 10)
    quarter_window = quarter_month and (day.day <= 10 or day.day >= 22)
    quarter_window |= day.month in (2, 5, 8, 11) and day.day <= 3
    times = [time(7, 50)]
    if quarter_window:
        times.extend((time(11, 20), time(16, 10)))
    if berlin.weekday() < 5:
        times.append(time(14, 20))
    return max((datetime.combine(day, slot, BERLIN) for slot in times if slot <= berlin.time()), default=None)


def published_matches(root, now):
    url = make_url(DEFAULT_URL, "publish-manifest.json", str(int(now.timestamp())), "watchdog")
    try:
        files = json.loads(fetch_bytes(url))["files"]
        for path in PUBLICATION_FILES:
            raw = (root / path).read_bytes()
            if files[path] != {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}:
                return False
    except (OSError, URLError, ValueError, KeyError, TypeError):
        return False
    return True


def plan(root, now, *, force=False, verify_publication=False):
    slot = latest_slot(now)
    result = {"eu": force, "uk": force, "publish": force, "slot": slot.isoformat() if slot else ""}
    if force or slot is None:
        return result
    for jurisdiction, filename in SNAPSHOTS.items():
        try:
            payload = json.loads((root / filename).read_text(encoding="utf-8"))
            complete = is_complete(payload, slot.date(), jurisdiction, since=slot)
        except (OSError, ValueError, AttributeError, TypeError):
            complete = False
        result[jurisdiction.lower()] = not complete
    result["publish"] = result["eu"] or result["uk"] or (verify_publication and not published_matches(root, now))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-publication", action="store_true")
    args = parser.parse_args()
    result = plan(ROOT, datetime.now(BERLIN), force=args.force, verify_publication=args.verify_publication)
    for key, value in result.items():
        print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")

if __name__ == "__main__":
    main()
