#!/usr/bin/env python3
"""Compatibility runner for the live EEX annual auction workbook.

The live 2026 workbook uses shorter headings than the DataSource interface
specification (for example: Date / Auction Price €/tCO2 / Auction Volume tCO2).
The EEX auction page can also insert a footnote marker immediately after the
2027 heading; this runner filters that marker from the supply summary.
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
import update_cbam_dashboard as base


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
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    result = {}
    for year in (2026, 2027):
        m = re.search(rf"(?:indicative\s+)?EUA\s+Volume\s+{year}(.*?)(?:EUA\s+Volume\s+20\d{{2}}|$)", text, re.I)
        if not m:
            continue
        nums = re.findall(r"\b\d[\d,.]*\b", m.group(1))
        vals = []
        for token in nums:
            digits = re.sub(r"[^0-9]", "", token)
            if digits:
                vals.append(int(digits))
        # EEX may show footnote marker '1' immediately after '2027'.
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


base.find_header_row = live_find_header_row
base.extract_supply_summary = live_extract_supply_summary
raise SystemExit(base.main())
