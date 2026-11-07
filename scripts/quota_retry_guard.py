"""Bounded, GitHub-only retry guard for missing EU/UK quota snapshots."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
ACTIVE = {"queued", "requested", "waiting", "pending", "in_progress"}
FAILED = {"failure", "timed_out"}


def retry_blocker(
    runs: list[dict],
    now: datetime,
    *,
    max_failures: int = 3,
    active_window_minutes: int = 90,
) -> str | None:
    """Return a reason not to dispatch; None means a retry is permitted.

    A successful gate-only workflow is not evidence of refreshed data. The
    caller must independently check dashboard_health before invoking this.
    """
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    today = now.astimezone(BERLIN).date()
    recent = now - timedelta(minutes=active_window_minutes)
    failures = 0
    for run in runs:
        stamp = str(run.get("createdAt") or "")
        try:
            created = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created.tzinfo is None or created > now:
            continue
        status = str(run.get("status") or "")
        if status in ACTIVE and created >= recent:
            return f"quota workflow already active since {stamp}"
        if created.astimezone(BERLIN).date() == today and run.get("conclusion") in FAILED:
            failures += 1
    if failures >= max_failures:
        return f"{failures} failed quota workflow runs today; retry cap {max_failures} reached"
    return None


def main() -> int:
    runs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    reason = retry_blocker(runs, datetime.now(timezone.utc))
    if reason:
        print(reason, flush=True)
        return 0  # caller skips dispatch
    print("quota retry permitted", flush=True)
    return 1  # caller dispatches


if __name__ == "__main__":
    raise SystemExit(main())
