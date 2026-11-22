#!/usr/bin/env python3
"""Update the public CBAM procurement dashboard from public official sources.

Primary source: EEX EUA Primary Market Auction Report (public XLSX).
Official CBAM prices: European Commission CBAM certificate price page.
The updater is defensive: secondary-source failures are recorded but do not overwrite
valid prior data with blanks.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
from zipfile import BadZipFile

from cbam_windows import SALES_START, build_window, calendar_days, mark_weeks, official_weeks
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "cbam" / "data"
CURRENT = DATA_DIR / "current.json"
HISTORY_DIR = DATA_DIR / "history"

UA = "Mozilla/5.0 (compatible; CBAMProcurementDashboard/1.0; +https://github.com/Davidzhu511/eu-taric-quota-dashboard)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
TIMEOUT = 40

EEX_AUCTION_REPORT = "https://public.eex-group.com/eex/eua-auction-report/emission-spot-primary-market-auction-report-{year}-data.xlsx"
EEX_AUCTION_PAGE = "https://www.eex.com/en/markets/environmentals/eu-ets1-eu-ets2-auctions/eu-ets1-auctions"
EEX_CBAM_PAGE = "https://www.eex.com/en/markets/environmentals/environmental-indices"
EC_CBAM_PRICE_PAGE = "https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/price-cbam-certificates_en"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get(url: str, *, binary: bool = False) -> bytes | str:
    r = SESSION.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content if binary else r.text


def norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).lower()


def as_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if isinstance(v, float) and math.isnan(v):
            return None
        return float(v)
    s = str(v).strip().replace("\u00a0", " ")
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def as_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v is None:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def find_header_row(ws):
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=min(ws.max_row, 100), values_only=True), start=1
    ):
        labels = [norm(v) for v in row]
        date_i = next((i for i, x in enumerate(labels) if x == "date" or "auction date" in x), None)
        price_i = next(
            (
                i for i, x in enumerate(labels)
                if "auction clearing price" in x
                or x.startswith("auction price")
                or "auction price €" in x
            ),
            None,
        )
        vol_i = next((i for i, x in enumerate(labels) if "auction volume" in x), None)
        if date_i is None or price_i is None or vol_i is None:
            continue

        mapping = {"date": date_i, "price": price_i, "volume": vol_i}
        status_i = next((i for i, x in enumerate(labels) if x == "status" or x.endswith(" status")), None)
        if status_i is not None:
            mapping["status"] = status_i
        contract_i = next((i for i, x in enumerate(labels) if x == "contract"), None)
        if contract_i is not None:
            mapping["contract"] = contract_i
        auction_i = next((i for i, x in enumerate(labels) if x in ("auction name", "auction")), None)
        if auction_i is not None:
            mapping["auction_name"] = auction_i
        return row_idx, mapping
    return None


def extract_supply_summary(html: str):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    result = {}
    for year in sorted(set(re.findall(r"EUA\s+Volume\s+(20\d{2})", text, re.I))):
        m = re.search(rf"(?:indicative\s+)?EUA\s+Volume\s+{year}(.*?)(?:EUA\s+Volume\s+20\d{{2}}|$)", text, re.I)
        if not m:
            continue
        nums = re.findall(r"\b\d[\d,.]*\b", m.group(1))
        vals = []
        for token in nums:
            digits = re.sub(r"[^0-9]", "", token)
            if digits:
                vals.append(int(digits))
        # EEX may show a footnote marker immediately after the year heading.
        while len(vals) > 4 and vals and vals[0] < 1000:
            vals.pop(0)
        if len(vals) >= 4:
            vals = vals[:4]
            result[str(year)] = {
                "cap_common": vals[0],
                "germany": vals[1],
                "poland": vals[2],
                "northern_ireland": vals[3],
                "total": sum(vals),
            }
    return result


def parse_auction_xlsx(content: bytes, cancelled: set | None = None) -> list[dict[str, Any]]:
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    found: list[dict[str, Any]] = []
    for ws in wb.worksheets:
        if re.search(r"ETS\s*2|EUAA|aviation", ws.title, re.I):
            continue
        header = find_header_row(ws)
        if not header:
            continue
        header_row, m = header
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            d = as_date(row[m["date"]] if m["date"] < len(row) else None)
            price = as_float(row[m["price"]] if m["price"] < len(row) else None)
            volume = as_float(row[m["volume"]] if m["volume"] < len(row) else None)
            status = str(row[m["status"]]).strip() if "status" in m and m["status"] < len(row) and row[m["status"]] is not None else ""
            if status and any(word in status.lower() for word in ("cancel", "abort", "fail")):
                if d and cancelled is not None:
                    cancelled.add(d.isoformat())
                continue
            if not d or not price or price <= 0 or not volume or volume <= 0:
                continue
            found.append({
                "date": d.isoformat(),
                "price": round(price, 4),
                "volume": int(round(volume)),
                "status": status,
                "contract": str(row[m["contract"]]).strip() if "contract" in m and m["contract"] < len(row) and row[m["contract"]] is not None else None,
                "auction_name": str(row[m["auction_name"]]).strip() if "auction_name" in m and m["auction_name"] < len(row) and row[m["auction_name"]] is not None else None,
            })
    wb.close()
    seen = set()
    deduped = []
    for item in sorted(found, key=lambda x: (x["date"], x.get("auction_name") or "", x["price"], x["volume"])):
        key = (item["date"], item.get("auction_name"), item["price"], item["volume"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def weighted_avg(rows: Iterable[dict[str, Any]]) -> float | None:
    rows = list(rows)
    total = sum(float(x["volume"]) for x in rows)
    if total <= 0:
        return None
    return sum(float(x["price"]) * float(x["volume"]) for x in rows) / total


def quarter_of(d: date) -> int:
    return (d.month - 1) // 3 + 1


def aggregate_auctions(auctions: list[dict[str, Any]]) -> dict[str, Any]:
    if not auctions:
        return {"latest": None, "weekly": [], "quarterly": [], "stats": {}}

    weekly_groups: dict[date, list[dict[str, Any]]] = defaultdict(list)
    quarterly_groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for a in auctions:
        d = date.fromisoformat(a["date"])
        monday = d - timedelta(days=d.weekday())
        weekly_groups[monday].append(a)
        quarterly_groups[(d.year, quarter_of(d))].append(a)

    weekly = []
    for monday, rows in sorted(weekly_groups.items()):
        weekly.append({
            "week_start": monday.isoformat(),
            "week_end": (monday + timedelta(days=6)).isoformat(),
            "price": round(weighted_avg(rows), 2),
            "volume": int(sum(r["volume"] for r in rows)),
            "auctions": len(rows),
        })

    quarterly = []
    for (year, q), rows in sorted(quarterly_groups.items()):
        quarterly.append({
            "year": year,
            "quarter": q,
            "price": round(weighted_avg(rows), 2),
            "volume": int(sum(r["volume"] for r in rows)),
            "auctions": len(rows),
            "complete": False,
        })

    prices = [float(a["price"]) for a in auctions]
    trailing_52_start = date.fromisoformat(auctions[-1]["date"]) - timedelta(days=365)
    trailing = [a for a in auctions if date.fromisoformat(a["date"]) >= trailing_52_start]
    trailing_prices = [float(a["price"]) for a in trailing] or prices
    last_20 = auctions[-20:]
    last_5 = auctions[-5:]
    latest_price = float(auctions[-1]["price"])
    ma20 = sum(float(a["price"]) for a in last_20) / len(last_20)
    ma5 = sum(float(a["price"]) for a in last_5) / len(last_5)
    low52, high52 = min(trailing_prices), max(trailing_prices)
    percentile = 0.5 if high52 == low52 else (latest_price - low52) / (high52 - low52)

    stats = {
        "latest_price": round(latest_price, 2),
        "latest_date": auctions[-1]["date"],
        "ma_5_auctions": round(ma5, 2),
        "ma_20_auctions": round(ma20, 2),
        "low_52w": round(low52, 2),
        "high_52w": round(high52, 2),
        "position_52w": round(percentile, 4),
        "last_5_vs_20": round((ma5 / ma20 - 1) if ma20 else 0, 4),
    }
    return {"latest": auctions[-1], "weekly": weekly[-80:], "quarterly": quarterly[-12:], "stats": stats}


def parse_price_table(html: str, year: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        cells = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
        if not cells:
            continue
        qcell = next((c for c in cells if re.search(rf"\bQ[1-4]\s*{year}\b", c, re.I)), None)
        if not qcell:
            continue
        q = int(re.search(r"Q([1-4])", qcell, re.I).group(1))
        price = None
        for c in reversed(cells):
            if re.fullmatch(r"\s*\d{1,3}[,.]\d{2}\s*", c):
                price = as_float(c)
                break
        pub_date = next((c for c in cells if re.search(r"\b\d{1,2}\s+[A-Za-z]+\s+20\d{2}\b", c)), None)
        out.append({"year": year, "quarter": q, "price": round(price, 2) if price is not None else None, "publication_date": pub_date})
    by_q = {x["quarter"]: x for x in out}
    return [by_q[q] for q in sorted(by_q)]


def load_previous() -> dict[str, Any]:
    try:
        return json.loads(CURRENT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fetch_auction_years(today, previous, errors):
    rows, cancelled, fresh = [], set(), False
    for year in (today.year - 1, today.year):
        key = str(year)
        old = [a for a in previous.get("auctions", []) if a["date"].startswith(key)]
        old_cancelled = {d for d in previous.get("cancelled_dates", []) if d.startswith(key)}
        try:
            cancelled_year = set()
            new = parse_auction_xlsx(get(EEX_AUCTION_REPORT.format(year=year), binary=True), cancelled_year)
            new = [a for a in new if a["date"].startswith(key) and a["date"] <= today.isoformat()]
            if not new and (old or year < today.year):
                raise ValueError("empty annual report")
            if {a["date"] for a in old} - {a["date"] for a in new} - cancelled_year:
                raise ValueError("annual report lost previously observed dates")
            rows.extend(new)
            cancelled.update(cancelled_year)
            if year == today.year:
                fresh = True
        except (requests.RequestException, ValueError, OSError, KeyError, BadZipFile) as exc:
            errors.append(f"EEX {year} auction report: {exc}")
            rows.extend(old)
            cancelled.update(old_cancelled)
    return sorted(rows, key=lambda a: a["date"]), cancelled, fresh


def fetch_calendars(page, today, previous, errors):
    first = today.year - 1
    result = {k: v for k, v in previous.get("auction_calendars", {}).items() if first <= int(k) <= today.year}
    candidates = {}
    for link in BeautifulSoup(page, "html.parser").select('tr a[href]'):
        href = link['href']
        label = link.find_parent('tr').get_text(" ", strip=True)
        match = re.search(r"Auction Calendar (20\d\d)\s*\(XLS", label, re.I)
        if not match or "ETS2" in label.upper() or not href.lower().endswith(".xlsx"):
            continue
        url = urljoin(EEX_AUCTION_PAGE, href)
        if urlsplit(url).hostname == "www.eex.com":
            candidates.setdefault(int(match[1]), url)
    current_ok = False
    for year in (first, today.year):
        key = str(year)
        url = candidates.get(year)
        if not url:
            if year == today.year:
                errors.append(f"EEX {year} auction calendar link unavailable")
            continue
        try:
            if result.get(key, {}).get("source") != url or year == today.year:
                result[key] = dict(source=url, days=calendar_days(get(url, binary=True), year))
            if year == today.year:
                current_ok = True
        except (requests.RequestException, ValueError, OSError, KeyError, BadZipFile) as exc:
            errors.append(f"EEX {year} auction calendar: {exc}")
    return result, current_ok


def fetch_commission(today, previous, errors):
    old = previous.get("official_cbam_prices", [])
    if any("EEX quarterly" in msg for msg in previous.get("meta", {}).get("errors", [])):
        old = []
    quarters = {q["quarter"]: q for q in old if q["year"] == 2026}
    weeks = {r["formation_week"]: r for r in previous.get("official_weekly_prices", [])}
    ok = False
    try:
        page = get(EC_CBAM_PRICE_PAGE)
        parsed = parse_price_table(page, 2026)
        for q in parsed:
            if q["price"] is not None or q["quarter"] not in quarters:
                quarters[q["quarter"]] = q
        if len(quarters) < 4 or (today >= date(2027, 1, 5) and quarters.get(4, {}).get("price") is None):
            errors.append("EC 2026 quarterly price table incomplete")
        updates = official_weeks(page)
        for r in updates:
            weeks[r["formation_week"]] = r
        ok = bool(updates) or today < SALES_START
        if not ok:
            errors.append("EC official weekly price table unavailable or unrecognised")
    except (requests.RequestException, ValueError) as exc:
        errors.append(f"EC official price page: {exc}")
    return [quarters[k] for k in sorted(quarters)], [weeks[k] for k in sorted(weeks)], ok


def main() -> int:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    previous = load_previous()
    now = now_utc()
    today = now.astimezone(ZoneInfo("Europe/Brussels")).date()
    errors = []
    auctions, cancelled, fresh = fetch_auction_years(today, previous, errors)
    if not auctions:
        raise RuntimeError("No current or archived auction evidence")
    try:
        page = get(EEX_AUCTION_PAGE)
    except requests.RequestException as exc:
        errors.append(f"EEX auction page: {exc}")
        page = ""
    supply = extract_supply_summary(page) or previous.get("auction_supply", {})
    calendars, calendar_ok = fetch_calendars(page, today, previous, errors)
    year_plan = calendars.get(str(today.year), {}).get("days", {})
    expected = {d for d, volume in year_plan.items() if volume and d <= today.isoformat()}
    if calendar_ok and expected:
        missing = expected - {a["date"] for a in auctions} - cancelled
        if missing:
            errors.append("EEX scheduled result missing: " + ", ".join(sorted(missing)[-3:]))
            fresh = False
    elif calendar_ok and not expected and not any(a["date"][:4] == str(today.year) for a in auctions):
        # Before the first scheduled sale a new annual auction report may not exist yet.
        errors = [e for e in errors if not e.startswith(f"EEX {today.year} auction report: 404")]
    quarterly, official, ec_ok = fetch_commission(today, previous, errors)
    agg = aggregate_auctions(auctions)
    mark_weeks(agg["weekly"], auctions, calendars, cancelled, today.isoformat())
    window = build_window(today, agg["weekly"], official, fresh and calendar_ok, calendars)
    if today >= SALES_START and window["current"] is None:
        errors.append("No unambiguous, in-force Commission weekly price for today")
    window["official_source_verified"] = ec_ok
    window["market_source_verified"] = fresh and calendar_ok
    window["actionable"] = (window["mode"] == "live" and ec_ok and window["current"] is not None
                            and window["next"] is not None)
    last_date = auctions[-1]["date"]
    payload = dict(
        meta=dict(checked_at=now.isoformat(), data_date=last_date, status="degraded" if errors else "ok",
                  errors=errors, methodology_version="3.0.0"),
        sources=dict(eex_auction_report=EEX_AUCTION_REPORT.format(year=today.year),
                     eex_auction_page=EEX_AUCTION_PAGE, eex_cbam_reference=EEX_CBAM_PAGE,
                     ec_cbam_price=EC_CBAM_PRICE_PAGE, price_regulation="https://eur-lex.europa.eu/eli/reg_impl/2025/2548/oj/eng"),
        official_cbam_prices=quarterly, official_weekly_prices=official, auction_supply=supply,
        auctions=auctions, cancelled_dates=sorted(cancelled), auction_calendars=calendars,
        auction_analytics=agg, procurement_window=window,
        public_score=dict(score=window["score"], max_score=100, model="60/40", mode=window["mode"]),
        model=dict(version="3.0.0", spread_max=60, history_max=40, history_weeks=26),
    )
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    CURRENT.write_text(data, encoding="utf-8")
    # Official prices may change on a day without an EUA auction.
    (HISTORY_DIR / f"{today.isoformat()}.json").write_text(data, encoding="utf-8")
    print(f"CBAM V3 {today}: {len(auctions)} auctions, mode={window['mode']}, score={window['score']}")
    for error in errors:
        print(f"WARNING: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
