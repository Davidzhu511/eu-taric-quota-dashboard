#!/usr/bin/env python3
"""Compatibility runner for the EEX auction workbook layout.

EEX's public annual workbook can place its tabular header below the first 30 rows.
Keep the core updater stable while widening header discovery for the live workbook.
"""
from __future__ import annotations

import update_cbam_dashboard as base


def wide_find_header_row(ws):
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=min(ws.max_row, 250), values_only=True), start=1
    ):
        labels = [base.norm(v) for v in row]
        date_i = next((i for i, x in enumerate(labels) if "auction date" in x), None)
        price_i = next((i for i, x in enumerate(labels) if "auction clearing price" in x), None)
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
        auction_i = next((i for i, x in enumerate(labels) if x == "auction name"), None)
        if auction_i is not None:
            mapping["auction_name"] = auction_i
        return row_idx, mapping
    return None


base.find_header_row = wide_find_header_row
raise SystemExit(base.main())
