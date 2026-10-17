#!/usr/bin/env python3
"""Compatibility runner and V2 scoring layer for the live CBAM dashboard.

The live EEX workbook uses shorter headings than the published interface
specification. This runner keeps the resilient parser overrides and replaces the
V1 procurement score with a V2 model designed to avoid two common errors:

1. rewarding a falling knife simply because prices are falling; and
2. double-counting highly correlated price signals.

V2 public layer (70 points):
- 52-week valuation: 20
- discount vs 13-week auction VWAP: 15
- stabilisation / reversal confirmation: 15
- completed-week auction supply momentum: 10
- next-year auction supply direction: 10

A separate research overlay contributes up to 30 points on the website.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from bs4 import BeautifulSoup
import update_cbam_dashboard as base

_SUPPLY_CACHE = {}


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def live_find_header_row(ws):
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=min(ws.max_row, 100), values_only=True), start=1
    ):
        labels = [base.norm(v) for v in row]
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


def live_extract_supply_summary(html: str):
    global _SUPPLY_CACHE
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    result = {}
    for year in (2026, 2027, 2028):
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
    _SUPPLY_CACHE = result
    return result


def v2_public_score(agg):
    stats = agg.get("stats") or {}
    if not stats:
        return {"score": None, "max_score": 70, "confidence": "low", "components": []}

    # 1) Absolute valuation in the trailing 52-week auction range (20).
    pos = float(stats.get("position_52w", 0.5))
    price_level = clip(20.0 * (1.0 - pos), 0.0, 20.0)

    # 2) Relative valuation versus the last 13 weekly auction VWAPs (15).
    weekly = agg.get("weekly") or []
    last_price = float(weekly[-1]["price"] if weekly else stats["latest_price"])
    recent_prices = [float(w["price"]) for w in weekly[-13:]]
    recent_avg = sum(recent_prices) / len(recent_prices) if recent_prices else last_price
    discount = (recent_avg - last_price) / recent_avg if recent_avg else 0.0
    relative_value = clip(7.5 + 7.5 * discount / 0.08, 0.0, 15.0)

    # 3) Stabilisation / reversal (15). V1 rewarded a negative trend. V2 does not.
    ma5 = float(stats.get("ma_5_auctions") or last_price)
    ma20 = float(stats.get("ma_20_auctions") or ma5)
    trend = (ma5 / ma20 - 1.0) if ma20 else 0.0
    latest_vs_ma5 = (float(stats["latest_price"]) / ma5 - 1.0) if ma5 else 0.0

    if trend <= -0.06:
        stability_base = 1.0
    elif trend < -0.015:
        stability_base = 1.0 + 8.0 * (trend + 0.06) / 0.045
    elif trend <= 0.03:
        stability_base = 9.0
    elif trend < 0.08:
        stability_base = 9.0 - 5.0 * (trend - 0.03) / 0.05
    else:
        stability_base = 4.0
    reversal_bonus = clip(3.0 + 3.0 * latest_vs_ma5 / 0.02, 0.0, 6.0)
    stabilisation = clip(stability_base + reversal_bonus, 0.0, 15.0)

    # 4) Recent auction supply momentum (10), using completed calendar weeks only.
    latest_date = date.fromisoformat(stats["latest_date"])
    current_monday = latest_date - timedelta(days=latest_date.weekday())
    complete_weeks = [w for w in weekly if date.fromisoformat(w["week_start"]) < current_monday]
    recent4 = complete_weeks[-4:]
    prior4 = complete_weeks[-8:-4]
    if len(recent4) == 4 and len(prior4) == 4:
        r = sum(float(w["volume"]) for w in recent4) / 4.0
        p = sum(float(w["volume"]) for w in prior4) / 4.0
        supply_change = (r / p - 1.0) if p else 0.0
        supply_momentum = clip(5.0 - 5.0 * supply_change / 0.20, 0.0, 10.0)
    else:
        supply_change = None
        supply_momentum = 5.0

    # 5) Structural next-year auction supply direction (10).
    y = latest_date.year
    cur = (_SUPPLY_CACHE.get(str(y)) or {}).get("total")
    nxt = (_SUPPLY_CACHE.get(str(y + 1)) or {}).get("total")
    if cur and nxt:
        structural_change = nxt / cur - 1.0
        structural_supply = clip(5.0 - 5.0 * structural_change / 0.10, 0.0, 10.0)
    else:
        structural_change = None
        structural_supply = 5.0

    score = price_level + relative_value + stabilisation + supply_momentum + structural_supply
    components = [
        {"name": "52周价格位置", "score": round(price_level, 1), "max": 20, "value": round(pos, 4), "note": "价格越靠近52周低位，估值分越高"},
        {"name": "相对13周均价折价", "score": round(relative_value, 1), "max": 15, "value": round(discount, 4), "note": "衡量当前周度拍卖均价相对中期基准是否便宜"},
        {"name": "止跌 / 反转确认", "score": round(stabilisation, 1), "max": 15, "value": round(trend, 4), "note": "持续下跌不再自动加分；横盘或反转后才提高采购分"},
        {"name": "已完成周拍卖供给动量", "score": round(supply_momentum, 1), "max": 10, "value": None if supply_change is None else round(supply_change, 4), "note": "排除本周未完成数据，避免假性供给收缩"},
        {"name": "下一年度拍卖供给方向", "score": round(structural_supply, 1), "max": 10, "value": None if structural_change is None else round(structural_change, 4), "note": "下一年度拍卖供应减少会提高提前采购分"},
    ]
    confidence = "high" if len(complete_weeks) >= 13 and cur and nxt else "medium"
    return {"score": round(score, 1), "max_score": 70, "confidence": confidence, "components": components}


def v2_analysis(payload):
    agg = payload["auction_analytics"]
    stats = agg.get("stats") or {}
    model = payload["public_score"]
    if not stats:
        return {"headline": "EEX拍卖数据暂不可用", "stance": "wait", "bullets": ["暂未取得有效的EEX一级拍卖记录。"]}

    s = float(model.get("score") or 0)
    if s >= 52:
        stance = "watch-positive"
        headline = "公共数据已接近较有吸引力区间，但仍需研究层确认后再提高采购覆盖率"
    elif s >= 38:
        stance = "neutral"
        headline = "公共数据中性，适合分批观察，不宜追价"
    else:
        stance = "minimum"
        headline = "公共数据暂不支持在合规需要之外加速采购"

    weekly = agg.get("weekly") or []
    latest_week = weekly[-1] if weekly else None
    quarter = agg.get("quarterly") or []
    current_q = quarter[-1] if quarter else None
    bullets = [
        f"最新EEX EUA一级拍卖清算价：€{stats['latest_price']:.2f}/tCO₂（{stats['latest_date']}）。",
        f"过去52周拍卖区间：€{stats['low_52w']:.2f}–€{stats['high_52w']:.2f}；当前位于自低点向上的约{stats['position_52w']*100:.0f}%位置。",
        "V2模型不再把单纯下跌视为买点；只有价格具有相对吸引力且出现止跌/反转确认，采购分才会明显上升。",
    ]
    if latest_week:
        bullets.append(f"本周截至最新拍卖的成交量加权均价：€{latest_week['price']:.2f}/tCO₂，共{latest_week['auctions']}场拍卖。")
    if current_q:
        bullets.append(f"本季度截至目前拍卖加权均价：€{current_q['price']:.2f}/tCO₂；在官方价格发布前仅作为透明跟踪值。")
    bullets.append("公共自动层最高70分；EUA远期曲线、政策/MSR、能源基本面和持仓/技术面由每日研究层补充至100分。")
    return {"headline": headline, "stance": stance, "bullets": bullets}


def stamp_v2_metadata():
    p = Path(base.CURRENT)
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    d.setdefault("meta", {})["methodology_version"] = "2.0.0"
    d["model"] = {
        "version": "2.0.0",
        "public_layer_max": 70,
        "research_layer_max": 30,
        "principle": "价格吸引力 + 止跌确认 + 拍卖供给；避免重复计权和 falling-knife 信号",
    }
    text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    p.write_text(text, encoding="utf-8")
    data_date = d.get("meta", {}).get("data_date")
    if data_date:
        hp = Path(base.HISTORY_DIR) / f"{data_date}.json"
        hp.write_text(text, encoding="utf-8")


base.find_header_row = live_find_header_row
base.extract_supply_summary = live_extract_supply_summary
base.score_from_public_data = v2_public_score
base.build_analysis = v2_analysis

rc = base.main()
stamp_v2_metadata()
raise SystemExit(rc)
