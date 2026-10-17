# CBAM Procurement Model V2

This file documents the public-data layer of the online dashboard.

## Public layer: 70 points

1. 52-week price valuation — 20 points
2. Discount versus 13-week auction VWAP — 15 points
3. Stabilisation / reversal confirmation — 15 points
4. Completed-week auction supply momentum — 10 points
5. Next-year auction supply direction — 10 points

Key design changes from V1:

- Falling prices no longer automatically increase the buy score. A strong downtrend receives a low stabilisation score until price action flattens or reverses.
- The old quarter-on-quarter price component is removed because it duplicated other price signals.
- Auction supply momentum excludes the current incomplete calendar week to prevent mid-week undercounting from producing a false scarcity signal.
- Structural next-year auction supply is scored separately from recent realised supply.
- The public layer remains capped at 70. The research overlay supplies up to 30 additional points from forward curve, policy/MSR, energy fundamentals and positioning/technical research.
- Final procurement coverage is shown only when a valid research overlay is available. Otherwise the dashboard shows a public-data observation signal rather than a final 100-point recommendation.
