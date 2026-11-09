# Steel quota dashboard: agent operating rules

Scope: EU tariff-quota categories 1A, 2, 4A, 4B; UK Category 4; related CBAM public research. GitHub Actions is responsible for deterministic extraction, validation and publishing. Never add daily LLM execution just to re-scrape the same data.

## Routine business analysis
- Daily ChatGPT tasks interpret meaningful quota changes from the latest available snapshots; they do not audit CI, poll deployment, trigger collection or repair workflows.
- Use the previous analysed version or a comparable historical snapshot; unchanged data needs no report. Unknown/stale values must not become zero balances or false changes.
- The existing GitHub watchdog owns freshness checks and bounded retries. Normal skips, queued work and upstream dates over a weekend are not failures. Report persistent business-impacting incidents once, not recurring technical tables.
- Content explanations must cite their data dates and official sources. A user-requested engineering repair is separate from routine business analysis.

## Trust and accuracy
- Read the latest main, actual failed GitHub Actions job and current snapshots before diagnosing. Do not treat an old chat result or successful job title as proof that live Pages contains new data.
- Preserve official order numbers, mapping, dates, values and source links unless authoritative EU/UK primary evidence supports change.
- Separate checked_at from official_update_date. Weekends or non-updated official data are not automatically failures.
- EU awaiting allocation is indicative; it cannot simply be deducted from available balance. Estimated blended duty for pending requests is not the entire quarter's universal duty.
- EU opening-day historical allocation rates must match the specific quarter, order number, origin and verifiable opening batch; later zero allocated percent must not erase valid opening evidence.
- For UK, unknown balance is not zero; fill rate or initial-minus-balance does not establish a same-day allocation ratio. Do not fabricate UK weighted duty.
- For uncertain inputs, fail visibly or label degraded; never weaken checks, falsify timestamps, or write a guessed value to obtain green CI.

## Engineering guardrails
- Prefer deterministic bounded retries and minimal code changes. Do not start a self-repair loop.
- Use a branch and PR. Run the relevant regression tests; require green checks. Changes to legislation interpretation, tariffs, origins, categories, quota calculations, workflows/security or publish controls require explicit review.
- A Pages deployment is verified only after publish-manifest.json identifies this specific run/attempt and every critical HTML/JSON fingerprint matches.
- Do not commit secrets, vendor personal data, or bypass permissions. Leave a durable error log and PR/issue reference if blocked.
- Keep ordinary data collection, builds, and deployment on GitHub Actions. AI should be invoked only on real incidents or user request.

## Skills
Read the relevant instructions before work:
- .agents/skills/quota-data-validation/SKILL.md
- .agents/skills/quota-incident-repair/SKILL.md
- .agents/skills/quota-policy-review/SKILL.md
