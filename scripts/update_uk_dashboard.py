#!/usr/bin/env python3
"""Fetch UK Category 4 steel tariff quota balances from the official UK dataset."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "uk"
HISTORY_DIR = DATA_DIR / "history"
CURRENT_FILE = DATA_DIR / "current.json"
HISTORY_INDEX_FILE = HISTORY_DIR / "index.json"

DATASET_PAGE = "https://www.data.gov.uk/dataset/4a478c7e-16c7-4c28-ab9b-967bb79342e9/uk-trade-quotas1"
LEGISLATION_URL = "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026"
IMPLEMENTATION_URL = "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/implementation-notifications-on-the-transitional-exemption-quota-administration-and-the-ukraine-exclusion"
BERLIN = ZoneInfo("Europe/Berlin")

# Exact Category 4 mapping from Table 4 of the UK steel trade measure.
QUOTAS: list[tuple[str, str, str, bool]] = [
    ("058604", "European Union", "欧盟", False),
    ("058605", "India", "印度", False),
    ("058606", "South Korea", "韩国", False),
    ("058607", "Vietnam", "越南", False),
    ("058608", "Residual", "其他国家（Residual；中国使用）", True),
]


def session() -> requests.Session:
    retry = Retry(total=3, connect=3, read=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504))
    client = requests.Session()
    client.mount("https://", HTTPAdapter(max_retries=retry))
    client.headers.update({"User-Agent": "Mozilla/5.0 (compatible; UK-Steel-Quota-Dashboard/1.0)", "Accept-Language": "en-GB,en;q=0.9"})
    return client


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def number(value: Any) -> float:
    token = str(value or "").strip()
    if not token or token.upper() in {"#NA", "NA", "N/A", "NONE"}:
        return 0.0
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return 0.0


def parse_iso(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def discover_latest_csv(client: requests.Session) -> tuple[str, str, str]:
    response = client.get(DATASET_PAGE, timeout=40)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[tuple[tuple[int, ...], str, str]] = []
    for link in soup.find_all("a", href=True):
        text = " ".join(link.stripped_strings)
        href = urljoin(response.url, link["href"])
        if "data.api.trade.gov.uk" not in href or "format=csv" not in href.lower():
            continue
        if "quotas-including-current" not in href:
            continue
        match = re.search(r"v(\d+(?:\.\d+)+)", text + " " + href, re.I)
        version = match.group(1) if match else "0"
        version_key = tuple(int(part) for part in version.split("."))
        candidates.append((version_key, version, href))
    if not candidates:
        raise RuntimeError("英国官方数据页未发现CSV下载链接")
    _, version, url = max(candidates, key=lambda item: item[0])
    page_date_match = re.search(r"Last updated:\s*</[^>]+>\s*([^<]+)", response.text, re.I)
    page_date = page_date_match.group(1).strip() if page_date_match else ""
    return url, version, page_date


def select_active(rows: list[dict[str, str]], order_number: str, today: date) -> dict[str, str]:
    matched = [row for row in rows if str(row.get("quota_order_number", "")).zfill(6) == order_number]
    if not matched:
        raise RuntimeError("官方CSV中未找到该Order Number")
    active = []
    for row in matched:
        start = parse_iso(row.get("quota_definition_validity_start_date", ""))
        end = parse_iso(row.get("quota_definition_validity_end_date", ""))
        if start and start <= today and (not end or today <= end):
            active.append((start, row))
    if active:
        return max(active, key=lambda pair: pair[0])[1]
    future = []
    for row in matched:
        start = parse_iso(row.get("quota_definition_validity_start_date", ""))
        if start and start > today:
            future.append((start, row))
    if future:
        return min(future, key=lambda pair: pair[0])[1]
    return max(matched, key=lambda row: row.get("quota_definition_validity_end_date", ""))


def row_to_item(row: dict[str, str], code: str, origin: str, origin_zh: str, china_pool: bool, csv_url: str) -> dict[str, Any]:
    initial = number(row.get("quota_definition_initial_volume"))
    balance = number(row.get("quota_definition_balance"))
    used = max(initial - balance, 0)
    used_pct = used / initial * 100 if initial else 0
    remaining_pct = balance / initial * 100 if initial else 0
    status = row.get("quota_definition_status", "")
    start = row.get("quota_definition_validity_start_date", "")
    end = row.get("quota_definition_validity_end_date", "")
    return {
        "jurisdiction": "UK",
        "category": "4",
        "code": code,
        "origin": origin,
        "origin_zh": origin_zh,
        "official_geographical_areas": row.get("quota_geographical_areas", ""),
        "validity_start_date": start,
        "validity_end_date": end,
        "validity_period": f"{start} — {end}" if start or end else "",
        "measurement_unit": row.get("quota_measurement_unit", ""),
        "initial_amount": round(initial, 3),
        "balance": round(balance, 3),
        "used_amount": round(used, 3),
        "used_percentage": round(used_pct, 4),
        "remaining_percentage": round(remaining_pct, 4),
        "fill_rate": round(number(row.get("quota_definition_fill_rate")) * 100, 4),
        "status": status,
        "last_allocation_date": row.get("quota_definition_last_allocation_date", ""),
        "blocking_periods": row.get("quota_definition_blocking_periods", ""),
        "suspension_periods": row.get("quota_definition_suspension_periods", ""),
        "commodities": row.get("quota_commodities", ""),
        "headings": row.get("quota_headings", ""),
        "out_of_quota_tariff_pct": 50,
        "china_uses_this_pool": china_pool,
        "source_url": csv_url,
        "stale": False,
        "error": "",
    }


def update_history_index() -> None:
    snapshots = [{"date": path.stem, "file": path.name} for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True) if path.name != "index.json"]
    atomic_write(HISTORY_INDEX_FILE, {"snapshots": snapshots})


def main() -> int:
    now = datetime.now(BERLIN)
    client = session()
    csv_url, version, page_date = discover_latest_csv(client)
    response = client.get(csv_url, timeout=120)
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{normalise_header(key): value for key, value in row.items()} for row in reader]
    if not rows:
        raise RuntimeError("英国官方CSV为空")

    items = []
    failures = []
    previous = {}
    if CURRENT_FILE.exists():
        try:
            previous = {item["code"]: item for item in json.loads(CURRENT_FILE.read_text(encoding="utf-8")).get("items", [])}
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            previous = {}

    for code, origin, origin_zh, china_pool in QUOTAS:
        try:
            row = select_active(rows, code, now.date())
            items.append(row_to_item(row, code, origin, origin_zh, china_pool, csv_url))
        except Exception as exc:
            message = str(exc).strip()
            failures.append({"category": "4", "code": code, "error": message})
            fallback = dict(previous.get(code, {}))
            fallback.update({"jurisdiction": "UK", "category": "4", "code": code, "origin": origin, "origin_zh": origin_zh, "china_uses_this_pool": china_pool, "out_of_quota_tariff_pct": 50, "stale": True, "error": message})
            items.append(fallback)

    successful = len(items) - len(failures)
    if successful == 0:
        raise RuntimeError("英国Category 4五个配额全部抓取失败")
    if [item.get("code") for item in items] != [item[0] for item in QUOTAS]:
        raise RuntimeError("英国配额编号顺序或完整性校验失败")
    for item, (_, origin, origin_zh, china_pool) in zip(items, QUOTAS):
        if item.get("origin") != origin or item.get("origin_zh") != origin_zh or bool(item.get("china_uses_this_pool")) != china_pool:
            raise RuntimeError(f"{item.get('code')}: 英国立法映射校验失败")

    active_periods = [item.get("validity_period", "") for item in items if not item.get("stale")]
    payload = {
        "meta": {
            "jurisdiction": "UK",
            "title": "英国钢铁Category 4配额看板",
            "checked_at": now.isoformat(timespec="seconds"),
            "official_update_date": page_date,
            "dataset_version": version,
            "validity_period": max(set(active_periods), key=active_periods.count) if active_periods else "",
            "source_url": csv_url,
            "dataset_page_url": DATASET_PAGE,
            "legislation_url": LEGISLATION_URL,
            "implementation_url": IMPLEMENTATION_URL,
            "mapping_basis": "UK steel trade measure from 1 July 2026 — Table 4",
            "successful_count": successful,
            "failed_count": len(failures),
            "total_count": len(QUOTAS),
            "out_of_quota_tariff_pct": 50,
            "warning": "英国公开余额可能滞后HMRC实际分配数日，不应用于锁定配额。",
        },
        "failures": failures,
        "items": items,
    }
    atomic_write(CURRENT_FILE, payload)
    snapshot_date = now.date().isoformat()
    atomic_write(HISTORY_DIR / f"{snapshot_date}.json", payload)
    update_history_index()
    print(f"Updated UK Category 4 {successful}/{len(QUOTAS)} from dataset v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
