#!/usr/bin/env python3
"""Fetch the current EU TARIC quota data and write static dashboard JSON."""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
CURRENT_FILE = DATA_DIR / "current.json"
HISTORY_INDEX_FILE = HISTORY_DIR / "index.json"

SEARCH_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp"
LIST_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/quota_list.jsp"
BERLIN = ZoneInfo("Europe/Berlin")

CODES: list[tuple[str, str, str]] = [
    ("1A", "099801", "Türkiye"),
    ("1A", "099802", "Japan"),
    ("1A", "099803", "India"),
    ("1A", "099804", "Taiwan"),
    ("1A", "099805", "Ukraine"),
    ("1A", "099806", "Korea"),
    ("1A", "099807", "Viet Nam"),
    ("1A", "099808", "Egypt"),
    ("1A", "099809", "Serbia"),
    ("1A", "099500", "FTA Quota - CSQ"),
    ("1A", "099701", "Brazil"),
    ("1A", "099705", "United Kingdom"),
    ("1A", "099702", "Indonesia"),
    ("1A", "099810", "Australia"),
    ("1A", "099811", "Saudi Arabia"),
    ("1A", "099704", "Switzerland"),
    ("1A", "099812", "Kazakhstan"),
    ("1A", "099703", "North Macedonia"),
    ("1A", "099600", "Other countries"),
    ("1A", "099700", "FTA Quota - Other countries"),
    ("2", "099817", "Taiwan"),
    ("2", "099818", "India"),
    ("2", "099819", "Korea"),
    ("2", "099820", "Türkiye"),
    ("2", "099821", "United Kingdom"),
    ("2", "099822", "Japan"),
    ("2", "099823", "Ukraine"),
    ("2", "099502", "FTA Quota - CSQ"),
    ("2", "099602", "Other countries"),
    ("2", "099707", "FTA Quota - Other countries"),
    ("2", "099709", "Egypt"),
    ("2", "099710", "Switzerland"),
    ("2", "099708", "Brazil"),
    ("4A", "099832", "Viet Nam"),
    ("4A", "099833", "Taiwan"),
    ("4A", "099834", "Türkiye"),
    ("4A", "099835", "India"),
    ("4A", "099836", "Korea"),
    ("4A", "099505", "FTA Quota - CSQ"),
    ("4A", "099605", "Other countries"),
    ("4A", "099714", "FTA Quota - Other countries"),
    ("4A", "099718", "United Kingdom"),
    ("4A", "099716", "Japan"),
    ("4A", "099715", "Egypt"),
    ("4A", "099717", "South Africa"),
    ("4B", "099837", "Korea"),
    ("4B", "099838", "China"),
    ("4B", "099839", "United Kingdom"),
    ("4B", "099840", "Türkiye"),
    ("4B", "099841", "India"),
    ("4B", "099506", "FTA Quota - CSQ"),
    ("4B", "099606", "Other countries"),
    ("4B", "099719", "FTA Quota - Other countries"),
    ("4B", "099720", "Egypt"),
    ("4B", "099721", "Switzerland"),
]


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; EU-TARIC-Quota-Dashboard/1.0)",
            "Accept-Language": "en-GB,en;q=0.9",
        }
    )
    return session


def soup_from_response(response: requests.Response) -> BeautifulSoup:
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def clean_text(value: Any) -> str:
    if hasattr(value, "stripped_strings"):
        value = " ".join(value.stripped_strings)
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_ddmmyyyy(value: str) -> date | None:
    match = re.search(r"(\d{2})-(\d{2})-(\d{4})", value or "")
    if not match:
        return None
    return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))


def parse_date(value: str) -> date | None:
    """Parse dates used by TARIC in both display text and detail URLs."""
    parsed = parse_ddmmyyyy(value)
    if parsed:
        return parsed
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def iso_from_ddmmyyyy(value: str) -> str:
    parsed = parse_ddmmyyyy(value)
    return parsed.isoformat() if parsed else value


def parse_number(value: str) -> float:
    match = re.search(r"-?[\d\s.,]+", value or "")
    if not match:
        return 0.0
    token = re.sub(r"\s+", "", match.group(0))
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif token.count(",") == 1 and len(token.rsplit(",", 1)[1]) <= 2:
        token = token.replace(",", ".")
    else:
        token = token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return 0.0


def extract_update_date(text: str) -> str:
    match = re.search(r"Last (?:tariff QUOTA|TARIC) update:\s*(\d{2}-\d{2}-\d{4})", text, re.I)
    return iso_from_ddmmyyyy(match.group(1)) if match else ""


def search_detail_url(session: requests.Session, code: str, today: date) -> tuple[str, str, bool]:
    candidates: list[dict[str, Any]] = []
    official_update = ""
    for year in (today.year, today.year + 1):
        # The consultation page loads result rows asynchronously from
        # quota_list.jsp. Querying the form page itself only returns the form.
        response = session.get(
            LIST_URL,
            params={
                "Lang": "en",
                "Origin": "",
                "Code": code,
                "Critical": "",
                "Status": "",
                "Year": str(year),
                "Expand": "false",
                "Offset": "0",
            },
            timeout=35,
        )
        soup = soup_from_response(response)
        official_update = official_update or extract_update_date(clean_text(soup))
        for link in soup.find_all("a", href=True):
            href = clean_text(link.get("href"))
            if "quota_tariff_details.jsp" not in href or f"Code={code}" not in href:
                continue
            detail_url = urljoin(response.url, href)
            query = parse_qs(urlparse(detail_url).query)
            start = parse_date((query.get("StartDate") or [""])[0])
            row = link.find_parent("tr")
            dates = [parse_ddmmyyyy(x) for x in re.findall(r"\d{2}-\d{2}-\d{4}", clean_text(row))]
            dates = [x for x in dates if x]
            end = dates[1] if len(dates) > 1 else None
            candidates.append({"url": detail_url, "start": start, "end": end})
        if any(c["start"] and c["start"] <= today and (not c["end"] or today <= c["end"]) for c in candidates):
            break

    if not candidates:
        raise RuntimeError("consultation 页面未返回有效期记录")

    active = [c for c in candidates if c["start"] and c["start"] <= today and (not c["end"] or today <= c["end"])]
    if active:
        chosen = max(active, key=lambda c: c["start"])
        not_yet_effective = False
    else:
        future = [c for c in candidates if c["start"] and c["start"] > today]
        if not future:
            raise RuntimeError("没有覆盖当天或未来的有效期记录")
        chosen = min(future, key=lambda c: c["start"])
        not_yet_effective = True
    return chosen["url"], official_update, not_yet_effective


def parse_detail(session: requests.Session, category: str, code: str, expected_origin: str, today: date) -> dict[str, Any]:
    detail_url, search_update, not_yet_effective = search_detail_url(session, code, today)
    response = session.get(detail_url, timeout=35)
    soup = soup_from_response(response)
    fields: dict[str, str] = {}
    wanted = (
        "Order number",
        "Validity period",
        "Origin",
        "Initial amount",
        "Amount",
        "Balance",
        "Exhaustion date",
        "Critical",
        "Last import date",
        "Last allocation date",
        "Total awaiting allocation",
        "Blocking period",
        "Suspension period",
        "Allocated percentage at the last allocation",
    )
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = clean_text(cells[0]).rstrip(":")
        key = next((candidate for candidate in wanted if label.startswith(candidate)), None)
        if key and key not in fields:
            fields[key] = clean_text(cells[1])

    if fields.get("Order number") != code:
        raise RuntimeError("详情页未返回目标 Order Number")

    initial = round(parse_number(fields.get("Initial amount", "")))
    amount = round(parse_number(fields.get("Amount", "")))
    balance = round(parse_number(fields.get("Balance", "")))
    awaiting = round(parse_number(fields.get("Total awaiting allocation", "")))
    allocated = parse_number(fields.get("Allocated percentage at the last allocation", ""))
    if initial <= 0:
        raise RuntimeError("初始配额为空或无法解析")

    awaiting_ratio = awaiting / initial if initial else 0.0
    remaining_pct = balance / initial * 100 if initial else 0.0
    outside_ratio = max(awaiting - balance, 0) / awaiting if awaiting else 0.0

    return {
        "category": category,
        "code": code,
        "expected_origin": expected_origin,
        # Use the regulation/PDF mapping as the dashboard label. TARIC often
        # prepends "European Union" or uses a generic pool description, which
        # is less useful than the origin wording in the governing table.
        "origin": expected_origin,
        "taric_origin": fields.get("Origin", ""),
        "validity_period": fields.get("Validity period", ""),
        "initial_amount_kg": initial,
        "amount_kg": amount,
        "balance_kg": balance,
        "awaiting_allocation_kg": awaiting,
        "awaiting_ratio": round(awaiting_ratio, 6),
        "remaining_percentage": round(remaining_pct, 4),
        "outside_ratio": round(outside_ratio, 6),
        "estimated_blended_tariff_pct": round(outside_ratio * 50, 4),
        "allocated_percentage": allocated,
        "critical": fields.get("Critical", ""),
        "exhaustion_date": fields.get("Exhaustion date", ""),
        "last_import_date": fields.get("Last import date", ""),
        "last_allocation_date": fields.get("Last allocation date", ""),
        "blocking_period": fields.get("Blocking period", ""),
        "suspension_period": fields.get("Suspension period", ""),
        "official_update_date": extract_update_date(clean_text(soup)) or search_update,
        "detail_url": response.url,
        "not_yet_effective": not_yet_effective,
        "stale": False,
        "error": "",
    }


def load_previous() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not CURRENT_FILE.exists():
        return {}, {}
    try:
        payload = json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
        items = {item["code"]: item for item in payload.get("items", []) if item.get("code")}
        return items, payload.get("meta", {})
    except (OSError, json.JSONDecodeError, TypeError):
        return {}, {}


def atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def most_common_nonempty(values: list[str]) -> str:
    filtered = [value for value in values if value]
    return Counter(filtered).most_common(1)[0][0] if filtered else ""


def update_history_index() -> None:
    snapshots = []
    for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        if path.name == "index.json":
            continue
        snapshots.append({"date": path.stem, "file": path.name})
    atomic_json_write(HISTORY_INDEX_FILE, {"snapshots": snapshots})


def validate_items(items: list[dict[str, Any]]) -> None:
    """Reject incomplete or internally inconsistent output before deployment."""
    expected_codes = [code for _, code, _ in CODES]
    actual_codes = [str(item.get("code", "")) for item in items]
    if actual_codes != expected_codes:
        raise RuntimeError("输出编号缺失、重复或顺序异常")

    expected_origins = {code: origin for _, code, origin in CODES}
    for item in items:
        code = str(item.get("code", ""))
        if item.get("origin") != expected_origins[code]:
            raise RuntimeError(f"{code}: 主原产地未使用 PDF 映射")

        initial = float(item.get("initial_amount_kg", 0) or 0)
        amount = float(item.get("amount_kg", 0) or 0)
        balance = float(item.get("balance_kg", 0) or 0)
        awaiting = float(item.get("awaiting_allocation_kg", 0) or 0)
        if min(initial, amount, balance, awaiting) < 0:
            raise RuntimeError(f"{code}: 配额数值不得为负数")
        if not item.get("stale") and initial <= 0:
            raise RuntimeError(f"{code}: 新抓取记录的初始配额无效")

        awaiting_ratio = awaiting / initial if initial else 0.0
        remaining_pct = balance / initial * 100 if initial else 0.0
        outside_ratio = max(awaiting - balance, 0) / awaiting if awaiting else 0.0
        tariff_pct = outside_ratio * 50
        checks = (
            ("待分配倍数", float(item.get("awaiting_ratio", 0) or 0), awaiting_ratio, 2e-6),
            ("剩余比例", float(item.get("remaining_percentage", 0) or 0), remaining_pct, 2e-4),
            ("配额外比例", float(item.get("outside_ratio", 0) or 0), outside_ratio, 2e-6),
            ("预估分摊税率", float(item.get("estimated_blended_tariff_pct", 0) or 0), tariff_pct, 2e-4),
        )
        for label, actual, expected, tolerance in checks:
            if abs(actual - expected) > tolerance:
                raise RuntimeError(f"{code}: {label}计算校验失败")

        detail_url = str(item.get("detail_url", ""))
        if detail_url:
            parsed = urlparse(detail_url)
            if parsed.scheme != "https" or parsed.netloc != "ec.europa.eu" or "quota_tariff_details.jsp" not in parsed.path:
                raise RuntimeError(f"{code}: 详情链接不是欧盟委员会官方地址")


def main() -> int:
    now = datetime.now(BERLIN)
    today = now.date()
    session = build_session()
    previous, previous_meta = load_previous()
    items: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    successful = 0

    for index, (category, code, expected_origin) in enumerate(CODES, start=1):
        print(f"[{index:02d}/{len(CODES)}] {category} {code} {expected_origin}", flush=True)
        try:
            item = parse_detail(session, category, code, expected_origin, today)
            items.append(item)
            successful += 1
        except Exception as exc:  # Keep the last good value but disclose the failure.
            message = clean_text(exc)
            failures.append({"category": category, "code": code, "error": message})
            if code in previous:
                item = dict(previous[code])
                item.update(
                    {
                        "category": category,
                        "expected_origin": expected_origin,
                        "origin": expected_origin,
                        "stale": True,
                        "error": message,
                    }
                )
                item.setdefault("not_yet_effective", False)
                items.append(item)
            else:
                items.append(
                    {
                        "category": category,
                        "code": code,
                        "expected_origin": expected_origin,
                        "origin": expected_origin,
                        "taric_origin": "",
                        "validity_period": "",
                        "initial_amount_kg": 0,
                        "amount_kg": 0,
                        "balance_kg": 0,
                        "awaiting_allocation_kg": 0,
                        "awaiting_ratio": 0,
                        "remaining_percentage": 0,
                        "outside_ratio": 0,
                        "estimated_blended_tariff_pct": 0,
                        "allocated_percentage": 0,
                        "critical": "",
                        "exhaustion_date": "",
                        "last_import_date": "",
                        "last_allocation_date": "",
                        "blocking_period": "",
                        "suspension_period": "",
                        "official_update_date": "",
                        "detail_url": "",
                        "not_yet_effective": False,
                        "stale": True,
                        "error": message,
                    }
                )
        time.sleep(0.15)

    if successful == 0:
        raise RuntimeError("55 个 Order Number 全部抓取失败，保留上一次已部署数据")

    validate_items(items)

    official_dates = [item.get("official_update_date", "") for item in items if not item.get("stale")]
    official_update_date = most_common_nonempty(official_dates) or str(previous_meta.get("official_update_date", ""))
    validity_period = most_common_nonempty([item.get("validity_period", "") for item in items if not item.get("stale")])
    blocking_period = most_common_nonempty([item.get("blocking_period", "") for item in items if not item.get("stale")])

    payload = {
        "meta": {
            "checked_at": now.isoformat(timespec="seconds"),
            "official_update_date": official_update_date,
            "validity_period": validity_period,
            "blocking_period": blocking_period,
            "source_url": SEARCH_URL + "?Lang=en",
            "successful_count": successful,
            "failed_count": len(failures),
            "total_count": len(CODES),
        },
        "failures": failures,
        "items": items,
    }

    atomic_json_write(CURRENT_FILE, payload)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", official_update_date):
        atomic_json_write(HISTORY_DIR / f"{official_update_date}.json", payload)
    else:
        print("Official update date unavailable; skipped dated history snapshot", flush=True)
    update_history_index()
    print(f"Updated {successful}/{len(CODES)} codes; failures={len(failures)}; official_date={official_update_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
