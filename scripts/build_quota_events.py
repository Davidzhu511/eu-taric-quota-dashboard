"""Build a rolling feed of verified changes in the published EU/UK snapshots."""

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {"EU": "current.json", "UK": "uk/current.json"}
CHINA_EU = {"099600", "099602", "099605", "099838"}
RETENTION_DAYS = 45


def read(path, default=None):
    if default is not None and not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def policy_for(period, rules):
    if not period:
        return None
    start, end = (datetime.strptime(part, "%d-%m-%Y").date().isoformat() for part in period.split(" - "))
    for rule in rules:
        if rule["from"] <= start <= end <= rule["through"]:
            return {"period": period, "status": "distribution_rules_verified", **rule}
    return {"period": period, "status": "distribution_rules_unverified", "sources": []}


def source_info(payload):
    meta = payload.get("meta", {})
    return {key: meta.get(key) for key in ("checked_at", "official_update_date", "dataset_version",
                                         "validity_period", "next_period", "source_url",
                                         "successful_count", "failed_count", "total_count", "pending_unknown_count")}


def observations(payload, jurisdiction):
    meta = payload.get("meta", {})
    uk_future = {row["code"]: row for row in payload.get("next_items", [])}
    for row in payload.get("items", []):
        if row.get("stale") or row.get("error") or row.get("not_yet_effective"):
            continue
        if not meta.get("validity_period") or row.get("validity_period") != meta["validity_period"]:
            continue
        eu = jurisdiction == "EU"
        balance = row.get("balance_kg" if eu else "balance")
        initial = row.get("initial_amount_kg" if eu else "initial_amount")
        status = row.get("status")
        if balance is None or not initial or str(status).casefold() in {"future", "expired"}:
            continue
        future = (row.get("next_period") or uk_future.get(row["code"]) or {})
        yield row["code"], {
            "category": row["category"], "origin": row["origin"], "period": row["validity_period"],
            "china_applicable": row["code"] in CHINA_EU if eu else bool(row.get("china_uses_this_pool")),
            "balance_kg": balance, "initial_kg": initial,
            "amount_kg": row.get("amount_kg"), "pending_kg": row.get("awaiting_allocation_kg"),
            "pressure": row.get("awaiting_to_balance_ratio"), "status": status,
            "blocking": row.get("blocking_period" if eu else "blocking_periods"),
            "suspension": row.get("suspension_period" if eu else "suspension_periods"),
            "future_period": future.get("validity_period"),
            "future_initial_kg": future.get("initial_amount_kg", future.get("initial_amount")),
            "checked_at": meta.get("checked_at"),
            "official_update_date": row.get("official_update_date") or meta.get("official_update_date"),
            "source_url": row.get("detail_url") or row.get("source_url") or meta.get("source_url"),
            "status_source_url": meta.get("implementation_url"),
        }


def change_types(before, after):
    old, new = before["balance_kg"], after["balance_kg"]
    if old > 0 and new == 0:
        yield "newly_exhausted"
    if old == 0 and new > 0:
        yield "positive_balance_after_zero"  # An increase alone never establishes reopened access.
    if 0 < new < old and (old - new >= max(2000_000, old * 0.2) or
                           new <= after["initial_kg"] * 0.02 < old):
        yield "material_balance_drop"
    old_pressure, new_pressure = before["pressure"], after["pressure"]
    if new > 0 and old_pressure is not None and new_pressure is not None:
        if any(old_pressure < limit <= new_pressure for limit in (0.7, 1)):
            yield "pending_pressure_increased"
    if after["amount_kg"] is not None and before["amount_kg"] is not None:
        if after["amount_kg"] > before["amount_kg"]:
            yield "official_quota_amount_increased"
    if new > after["initial_kg"] and new > old and after["amount_kg"] is None:
        yield "balance_above_initial_increased"
    if any(before[field] != after[field] for field in ("status", "blocking", "suspension")):
        yield "official_status_changed"
    if after["future_period"] and any(before[key] != after[key] for key in ("future_period", "future_initial_kg")):
        yield "future_initial_changed"


def event(day, jurisdiction, kind, code, before, after):
    def semantic(value):
        return {key: field for key, field in (value or {}).items()
                if key not in {"checked_at", "source_url", "status_source_url", "dataset_version", "evidence"}}

    identity = [jurisdiction, kind, code, semantic(before), semantic(after)]
    ident = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    return dict(id=ident, observed_on=day.isoformat(), jurisdiction=jurisdiction, kind=kind,
                code=code, before=before, after=after)


def opening_batches(summary):
    return {(r["code"], r["validity_period"]): {k: r.get(k) for k in (
        "code", "category", "origin", "validity_period", "status", "declaration_date", "allocation_date",
        "allocation_pct", "weighted_duty_pct", "official_update_date", "evidence")}
        for r in summary.get("eu", []) if r["status"] in {"historical_allocation", "conflicting_evidence"}}


def build(data, previous_dir, rules):
    archive = read(data / "quota-events.json", {})
    sources, payloads, previous = {}, {}, {}
    candidates = []
    for jurisdiction, filename in FILES.items():
        payload = payloads[jurisdiction] = read(data / filename)
        old = previous[jurisdiction] = read(previous_dir / filename, {})
        sources[jurisdiction] = source_info(payload)
        candidates.extend([source_info(payload).get("checked_at") or "", source_info(old).get("checked_at") or ""])
    observed = date.fromisoformat(max(candidates)[:10])
    earliest = (observed - timedelta(days=RETENTION_DAYS - 1)).isoformat()
    events = {e["id"]: e for e in archive.get("events", []) if e["observed_on"] >= earliest}

    def record(jurisdiction, kind, code, before, after):
        row = event(observed, jurisdiction, kind, code, before, after)
        events.setdefault(row["id"], row)

    for jurisdiction, payload in payloads.items():
        old = previous[jurisdiction]
        prior = source_info(old)
        current = sources[jurisdiction]
        if current == prior and payload == old:
            continue
        latest = dict(observations(payload, jurisdiction))
        if not latest:
            continue
        if jurisdiction == "EU" and policy_for(current["validity_period"], rules)["status"] != "distribution_rules_verified":
            for row in latest.values():
                row["china_applicable"] = None
        if prior["validity_period"] and current["validity_period"] != prior["validity_period"]:
            record(jurisdiction, "period_opened", None, prior, current)
            continue
        old_items = dict(observations(old, jurisdiction))
        missing = latest.keys() - old_items.keys()
        history = data / Path(FILES[jurisdiction]).parent / "history"
        for path in sorted(history.glob("20*.json"), reverse=True):
            if not missing:
                break
            snapshot = read(path)
            if not prior["checked_at"] or (source_info(snapshot)["checked_at"] or "") > prior["checked_at"]:
                continue
            for code, row in observations(snapshot, jurisdiction):
                if code in missing and row["period"] == latest[code]["period"]:
                    old_items[code] = row
                    missing.remove(code)
        for code, after in latest.items():
            before = old_items.get(code)
            if before is None or before["period"] != after["period"]:
                continue
            if after["china_applicable"] is None:
                before["china_applicable"] = None
            for kind in change_types(before, after):
                record(jurisdiction, kind, code, before, after)

    previous_batches = opening_batches(read(previous_dir / "quarterly-summary.json", {}))
    for key, row in opening_batches(read(data / "quarterly-summary.json")).items():
        old = previous_batches.get(key)
        if old is None or (old["status"], old["allocation_pct"]) != (row["status"], row["allocation_pct"]):
            record("EU", "opening_allocation_evidence", key[0], old, row)

    eu_policy = {key: policy_for(sources["EU"][field], rules)
                 for key, field in (("current", "validity_period"), ("next", "next_period"))}
    for key, details in eu_policy.items():
        old = archive.get("eu_policy", {}).get(key)
        if details and details != old:
            record("EU", f"{key}_period_policy_status", None, old, details)

    return dict(schema=1, retention_days=RETENTION_DAYS, sources=sources, eu_policy=eu_policy,
                events=sorted(events.values(), key=lambda row: (row["observed_on"], row["id"]), reverse=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-dir", required=True, type=Path)
    args = parser.parse_args()
    data = ROOT / "data"
    result = build(data, args.previous_dir, read(data / "quota-policy.json"))
    output = data / "quota-events.json"
    tmp = output.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)
    print(f"Quota events: {len(result['events'])} retained")


if __name__ == "__main__":
    main()
