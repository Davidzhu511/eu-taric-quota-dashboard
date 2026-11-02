---
name: quota-incident-repair
description: Diagnose Actions or website deployment failures, reproduce them, and propose a minimum safe GitHub pull request.
---

# Bounded repair workflow

1. Fetch latest main, failing workflow run and failing job logs; determine whether network, official HTML/CSV shape, parser, quarterly transition, git race or Pages publication is responsible.
2. Transient official HTTP failures: attempt bounded retry. Do not summon an LLM repeatedly for transient problems.
3. Real parser/regression: preserve a sanitized fixture showing the bad response, write a failing deterministic test, patch the smallest affected function.
4. Run test suite and bilingual site build; don't bypass source checks, suppress errors, reset history, or change official mapping/rates to make tests pass.
5. Create a branch and PR detailing root cause, evidence, effect, tests and remaining uncertainty. CI success is necessary but not sufficient for policy-sensitive changes.
6. Verify Pages via the deployment manifest run ID and HTML/JSON hashes; no verified result means no success claim.
7. Stop after one AI patch attempt per incident unless a human explicitly authorizes further work.

Never silently auto-merge edits to steel tariff policy, origin applicability, calculations, GitHub workflow security, or data provenance.
