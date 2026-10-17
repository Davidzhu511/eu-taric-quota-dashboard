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


def find_header_row(ws) -> tuple[int, dict[str, int]] | None:
    for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row, 30), values_only=True), start=1):
        labels = [norm(v) for v in row]
        date_i = next((i for i, x in enumerate(labels) if "auction date" in x), None)
        price_i = next((i for i, x in enumerate(labels) if "auction clearing price" in x), None)
        vol_i = next((i for i, x in enumerate(labels) if "auction volume" in x), None)
        if date_i is not None and price_i is not None and vol_i is not None:
            mapping = {"date": date_i, "price": price_i, "volume": vol_i}
            status_i = next((i for i, x in enumerate(labels) if x == "status" or x.endswith(" status")), None)
            if status_i is not None:
                mapping["status"] = status_i
            contract_i = next((i for i, x in enumerate(labels) if x == "contract"), None)
            if contract_i is not None:
                mapping["contract"] = contract_i
            auction_i = next((i for i, x in enumerate(labels) if x == "auction name"), None)
            if auction_i is not None:
                mapping["auction_name"] = auction_i
            return row_idx, mapping
    return None


def parse_auction_xlsx(content: bytes) -> list[dict[str, Any]]:
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    found: list[dict[str, Any]] = []
    for ws in wb.worksheets:
        header = find_header_row(ws)
        if not header:
            continue
        header_row, m = header
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            d = as_date(row[m["date"]] if m["date"] < len(row) else None)
            price = as_float(row[m["price"]] if m["price"] < len(row) else None)
            volume = as_float(row[m["volume"]] if m["volume"] < len(row) else None)
            status = str(row[m["status"]]).strip() if "status" in m and m["status"] < len(row) and row[m["status"]] is not None else ""
            if not d or price is None or volume is None or volume <= 0:
                continue
            if status and any(word in status.lower() for word in ("cancel", "abort", "fail")):
                continue
            found.append({
                "date": d.isoformat(),
                "price": round(price, 4),
                "volume": int(round(volume)),
                "status": status,
                "contract": str(row[m["contract"]]).strip() if "contract" in m and m["contract"] < len(row) and row[m["contract"]] is not None else None,
                "auction_name": str(row[m["auction_name"]]).strip() if "auction_name" in m and m["auction_name"] < len(row) and row[m["auction_name"]] is not None else None,
            })
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


def fetch_official_prices(year: int) -> tuple[list[dict[str, Any]], list[str]]:
    errors = []
    prices: list[dict[str, Any]] = []
    try:
        html = get(EC_CBAM_PRICE_PAGE)
        prices = parse_price_table(html, year)
    except Exception as exc:
        errors.append(f"European Commission price page: {exc}")
    if not any(x.get("price") is not None for x in prices):
        try:
            html = get(EEX_CBAM_PAGE)
            fallback = parse_price_table(html, year)
            if fallback:
                prices = fallback
                errors.append("Official Commission table unavailable; showing EEX quarterly cross-check values where available.")
        except Exception as exc:
            errors.append(f"EEX quarterly fallback: {exc}")
    return prices, errors


def extract_supply_summary(html: str) -> dict[str, Any]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    result: dict[str, Any] = {}
    for year in (2026, 2027):
        m = re.search(rf"(?:indicative\s+)?EUA\s+Volume\s+{year}\s+([0-9,\.]+)\s+([0-9,\.]+)\s+([0-9,\.]+)\s+([0-9,\.]+)", text, re.I)
        if m:
            nums = [int(re.sub(r"[^0-9]", "", x)) for x in m.groups()]
            result[str(year)] = {"cap_common": nums[0], "germany": nums[1], "poland": nums[2], "northern_ireland": nums[3], "total": sum(nums)}
    return result


def score_from_public_data(agg: dict[str, Any]) -> dict[str, Any]:
    stats = agg.get("stats") or {}
    if not stats:
        return {"score": None, "max_score": 70, "confidence": "low", "components": []}
    pos = float(stats.get("position_52w", 0.5))
    price_attract = max(0.0, min(25.0, 25.0 * (1 - pos)))

    weekly = agg.get("weekly") or []
    last_price = weekly[-1]["price"] if weekly else stats["latest_price"]
    recent_prices = [w["price"] for w in weekly[-13:]]
    recent_avg = sum(recent_prices) / len(recent_prices) if recent_prices else last_price
    discount = (recent_avg - last_price) / recent_avg if recent_avg else 0
    recent_discount = max(0.0, min(15.0, 7.5 + 7.5 * discount / 0.08))

    trend = float(stats.get("last_5_vs_20", 0))
    short_trend = max(0.0, min(10.0, 5.0 - 5.0 * trend / 0.06))

    recent4 = weekly[-4:]
    prior4 = weekly[-8:-4]
    if recent4 and prior4:
        r = sum(w["volume"] for w in recent4) / len(recent4)
        p = sum(w["volume"] for w in prior4) / len(prior4)
        vol_change = (r / p - 1) if p else 0
        supply = max(0.0, min(10.0, 5.0 - 5.0 * vol_change / 0.20))
    else:
        vol_change, supply = 0.0, 5.0

    q = agg.get("quarterly") or []
    if len(q) >= 2 and q[-2]["price"]:
        qchg = q[-1]["price"] / q[-2]["price"] - 1
        quarter_signal = max(0.0, min(10.0, 5.0 - 5.0 * qchg / 0.10))
    else:
        qchg, quarter_signal = 0.0, 5.0

    score = price_attract + recent_discount + short_trend + supply + quarter_signal
    components = [
        {"name": "52-week price attractiveness", "score": round(price_attract, 1), "max": 25},
        {"name": "discount vs 13-week auction average", "score": round(recent_discount, 1), "max": 15, "value": round(discount, 4)},
        {"name": "short-term auction price trend", "score": round(short_trend, 1), "max": 10, "value": round(trend, 4)},
        {"name": "auction supply momentum", "score": round(supply, 1), "max": 10, "value": round(vol_change, 4)},
        {"name": "quarter-on-quarter auction price", "score": round(quarter_signal, 1), "max": 10, "value": round(qchg, 4)},
    ]
    return {"score": round(score, 1), "max_score": 70, "confidence": "medium", "components": components}


def build_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    agg = payload["auction_analytics"]
    stats = agg.get("stats") or {}
    score = payload["public_score"]
    if not stats:
        return {"headline": "Data unavailable", "stance": "wait", "bullets": ["No valid EEX auction rows were available."]}

    s = score.get("score") or 0
    if s >= 50:
        stance = "accumulate"
        headline = "Public auction data are moving toward a more attractive procurement window"
    elif s >= 35:
        stance = "neutral"
        headline = "Public auction data are neutral; use staged purchasing rather than chasing price"
    else:
        stance = "minimum"
        headline = "Public auction data do not justify accelerating purchases beyond compliance needs"

    weekly = agg.get("weekly") or []
    latest_week = weekly[-1] if weekly else None
    quarter = agg.get("quarterly") or []
    current_q = quarter[-1] if quarter else None
    bullets = [
        f"Latest EEX auction clearing price: €{stats['latest_price']:.2f}/tCO₂ on {stats['latest_date']}.",
        f"Trailing 52-week auction range: €{stats['low_52w']:.2f}–€{stats['high_52w']:.2f}; current position {stats['position_52w']*100:.0f}% from the low.",
    ]
    if latest_week:
        bullets.append(f"Current-week auction VWAP estimate: €{latest_week['price']:.2f}/tCO₂ across {latest_week['auctions']} auctions.")
    if current_q:
        bullets.append(f"Current-quarter auction VWAP estimate: €{current_q['price']:.2f}/tCO₂; this is an estimate until the Commission publishes the official price where applicable.")
    bullets.append("The automated public-data score is capped at 70/100. Forward-curve, policy/MSR, energy and positioning overlays require separate research and should not be inferred from this number alone.")
    return {"headline": headline, "stance": stance, "bullets": bullets}


def load_previous() -> dict[str, Any]:
    try:
        return json.loads(CURRENT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    previous = load_previous()
    checked_at = now_utc()
    year = checked_at.year
    errors: list[str] = []

    auctions: list[dict[str, Any]] = []
    auction_url = EEX_AUCTION_REPORT.format(year=year)
    try:
        content = get(auction_url, binary=True)
        auctions = parse_auction_xlsx(content)
        if not auctions:
            raise RuntimeError("no auction rows parsed")
    except Exception as exc:
        errors.append(f"EEX auction report: {exc}")
        auctions = previous.get("auctions", [])

    official, official_errors = fetch_official_prices(year)
    errors.extend(official_errors)
    if not official and previous.get("official_cbam_prices"):
        official = previous["official_cbam_prices"]

    supply = {}
    try:
        supply = extract_supply_summary(get(EEX_AUCTION_PAGE))
    except Exception as exc:
        errors.append(f"EEX auction page supply summary: {exc}")
        supply = previous.get("auction_supply", {})

    analytics = aggregate_auctions(auctions)
    public_score = score_from_public_data(analytics)
    payload: dict[str, Any] = {
        "meta": {
            "checked_at": checked_at.isoformat(),
            "data_date": analytics.get("stats", {}).get("latest_date"),
            "status": "ok" if auctions else "degraded",
            "errors": errors,
            "methodology_version": "1.0.0",
        },
        "sources": {
            "eex_auction_report": auction_url,
            "eex_auction_page": EEX_AUCTION_PAGE,
            "eex_cbam_reference": EEX_CBAM_PAGE,
            "ec_cbam_price": EC_CBAM_PRICE_PAGE,
        },
        "official_cbam_prices": official,
        "auction_supply": supply,
        "auctions": auctions[-400:],
        "auction_analytics": analytics,
        "public_score": public_score,
    }
    payload["analysis"] = build_analysis(payload)

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    CURRENT.write_text(text, encoding="utf-8")
    hist_date = analytics.get("stats", {}).get("latest_date") or checked_at.date().isoformat()
    (HISTORY_DIR / f"{hist_date}.json").write_text(text, encoding="utf-8")

    print(f"CBAM dashboard updated: {len(auctions)} auctions, status={payload['meta']['status']}, errors={len(errors)}")
    for err in errors:
        print(f"WARNING: {err}", file=sys.stderr)
    return 0 if auctions else 1


if __name__ == "__main__":
    raise SystemExit(main())
