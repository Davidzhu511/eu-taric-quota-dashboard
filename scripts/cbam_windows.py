"""CBAM weekly sale windows and public procurement score (EUR per certificate)."""
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO
import re

from bs4 import BeautifulSoup
from openpyxl import load_workbook

DAY = timedelta(days=1)
WEEK = timedelta(days=7)
SALES_START = date(2027, 2, 1)
# Commission Brussels working days, OJ C/2025/4102. Unknown years require
# explicit official validity dates; never substitute a national holiday calendar.
HOLIDAYS = {2027: {"01-01", "03-25", "03-26", "03-29", "05-06", "05-07", "05-17",
                   "07-21", "11-01", "11-02", *(f"12-{d}" for d in range(23, 32))}}


def monday(day):
    return day - timedelta(days=day.weekday())


def first_workday(day):
    while day.year in HOLIDAYS:
        if day.weekday() < 5 and day.strftime("%m-%d") not in HOLIDAYS[day.year]:
            return day
        day += DAY
    return None


def parse_day(value):
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def official_weeks(html):
    """Read EC price tables by named columns; quarterly rows are never weekly quotes."""
    quotes = {}
    for table in BeautifulSoup(html, "html.parser").select("table"):
        rows = table.select("tr")
        if not rows:
            continue
        header = [c.get_text(" ", strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        def column(pattern):
            return next((i for i, h in enumerate(header) if re.search(pattern, h)), None)
        price = column(r"price")
        published = column(r"publication|published")
        start = column(r"valid from|applicable from|start of application|effective from")
        end = column(r"valid (?:to|until|through)|applicable (?:until|to)|end of application")
        period = column(r"week|period of application|validity period")
        if price is None or published is None or (period is None and start is None):
            continue
        for row in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if len(cells) != len(header) or not re.fullmatch(r"(?:€\s*)?\d{1,5}(?:[.,]\d{1,2})?", cells[price]):
                continue
            pub = parse_day(cells[published])
            if not pub or pub.year < 2027 or any(re.search(r"\bQ[1-4]\b", c, re.I) for c in cells):
                continue
            valid_from = parse_day(cells[start]) if start is not None else first_workday(pub + DAY)
            valid_to = parse_day(cells[end]) if end is not None else first_workday(monday(pub) + WEEK)
            if period is not None and ("application" in header[period] or "validity" in header[period]):
                interval = re.split(r"\s+[–—-]\s+|\s+to\s+|[–—]", cells[period], maxsplit=1)
                if len(interval) == 2:
                    valid_from, valid_to = (parse_day(d.strip()) for d in interval)
            if not valid_from or not valid_to or not pub < valid_from <= valid_to:
                continue
            formation = monday(pub) - WEEK
            value = float(cells[price].replace("€", "").replace(",", ".").strip())
            if value <= 0:
                continue
            item = dict(price=value, formation_week=formation.isoformat(), published=pub.isoformat(),
                        valid_from=valid_from.isoformat(), valid_to=valid_to.isoformat(), kind="official")
            key = formation.isoformat()
            if key in quotes and quotes[key] != item:
                raise ValueError(f"conflicting EC weekly prices: {key}")
            quotes[key] = item
    return list(quotes.values())


def calendar_days(blob, year):
    """Use consolidated daily volumes rather than summing country shares."""
    wb = load_workbook(BytesIO(blob), read_only=True, data_only=True)
    days = {}
    dates = ()
    for row in wb["Details_EUA"].values:
        if row[0] == "Date":
            dates = row
        elif str(row[0]).rstrip(" *") == "Consolidated Volume" and dates:
            for day, volume in zip(dates, row):
                if isinstance(day, datetime) and day.year == year:
                    if volume not in (None, "") and (type(volume) not in (int, float) or volume < 0):
                        raise ValueError("unexpected calendar volume")
                    days[day.date().isoformat()] = int(volume or 0)
            dates = ()
    wb.close()
    if not days or not any(days.values()):
        raise ValueError(f"missing {year} EUA calendar")
    return days


def mark_weeks(weekly, auctions, calendars, cancelled, due_through):
    by_day = Counter()
    counts = Counter()
    for row in auctions:
        by_day[row["date"]] += row["volume"]
        counts[row["date"]] += 1
    for w in weekly:
        start = date.fromisoformat(w["week_start"])
        dates = [(start + n * DAY).isoformat() for n in range(7)]
        planned = {}
        for d in dates:
            year_plan = calendars.get(d[:4], {}).get("days", {})
            if year_plan.get(d, 0):
                planned[d] = year_plan[d]
        w["planned_volume"] = sum(planned.values()) or None
        w["planned_auctions"] = len(planned) or None
        # Calendar files describe one consolidated scheduled auction per listed day.
        missing_due = any(d <= due_through and not by_day[d] and d not in cancelled for d in planned)
        matches = bool(planned) and not missing_due and all(not by_day[d] or (counts[d] == 1 and by_day[d] == planned.get(d)) for d in dates)
        accounted = matches and all(by_day[d] or d in cancelled for d in planned)
        w["complete"] = bool(accounted)
        w["eligible_estimate"] = bool(accounted or (matches and w["auctions"] >= 3
                                      and w["volume"] * 3 >= sum(planned.values()) * 2))


def auction_quote(week, weeks):
    row = weeks.get(week)
    if not row or not row["eligible_estimate"]:
        return None
    return dict(price=row["price"], formation_week=week.isoformat(),
                kind="complete_estimate" if row["complete"] else "partial_estimate",
                auctions=row["auctions"], volume=row["volume"], planned_volume=row["planned_volume"])


def score_window(p, n, weekly):
    result = dict(score=None, max_score=100, spread=None, impact_per_1000=None, threshold=None,
                  spread_points=None, history_points=None, percentile=None, history_weeks=0, direction=None)
    if not p:
        return result
    price = p["price"]
    threshold = max(2.0, price * .02)
    result["threshold"] = round(threshold, 4)
    prior = [w for w in weekly if w["week_start"] < p["formation_week"]][-26:]
    result["history_weeks"] = sum(bool(w["complete"]) for w in prior)
    if result["history_weeks"] == 26:
        rank = sum((w["price"] < price) + 0.5 * (w["price"] == price) for w in prior) / 26
        result.update(percentile=round(rank, 4), history_points=round(40 * (1 - rank), 1))
    if n:
        spread = round(n["price"] - price, 2)
        points = min(60, max(0, 30 + 30 * spread / threshold))
        direction = ("current_cheaper" if spread > 0 else "next_cheaper") if abs(spread) >= threshold else "within_threshold"
        result.update(spread=spread, impact_per_1000=round(spread * 1000), spread_points=round(points, 1), direction=direction)
        if result["history_weeks"] == 26:
            result["score"] = round(points + 40 * (1 - rank), 1)
    return result


def empty_auction_week(target, calendars):
    days = [target + n * DAY for n in range(5)]
    return all(calendars.get(str(d.year), {}).get("days", {}).get(d.isoformat()) == 0 for d in days)


def build_window(today, weekly, official, market_fresh=True, calendars=None):
    simulation = today < SALES_START
    observed = [r for r in official if r["published"] <= today.isoformat()]
    active = [r for r in observed if r["valid_from"] <= today.isoformat() <= r["valid_to"]]
    current = active[0] if len(active) == 1 else None
    weeks = {date.fromisoformat(w["week_start"]): w for w in weekly}
    current_week = monday(today)
    if simulation and today.year < 2027:
        # Historical replay uses normal Tuesday changeovers solely as simulation.
        anchor = current_week - (2 if today.weekday() == 0 else 1) * WEEK
        candidate = auction_quote(anchor, weeks) if market_fresh else None
        if candidate and candidate["kind"] == "complete_estimate":
            current = candidate
    following = None
    if current:
        target = date.fromisoformat(current["formation_week"]) + WEEK
        following = next((r for r in observed if r["formation_week"] == target.isoformat()
                          and r["valid_from"] > today.isoformat()), None)
        if not following and market_fresh:
            following = auction_quote(target, weeks)
            # Article 21(1) carries the last auction week across a week with no scheduled auctions.
            if not following and calendars and empty_auction_week(target, calendars):
                earlier = sorted((w for w in weeks if w < target), reverse=True)
                if earlier and weeks[earlier[0]]["complete"]:
                    following = dict(price=weeks[earlier[0]]["price"], kind="no_auctions_estimate",
                                     formation_week=target.isoformat(), reference_week=earlier[0].isoformat())
    last_day = current.get("valid_to") if current else None
    switch = first_workday(date.fromisoformat(last_day) + DAY) if last_day else None
    next_start = following.get("valid_from") if following else None
    return dict(as_of=today.isoformat(), next_effective_from=next_start or (switch.isoformat() if switch else None), mode="simulation" if simulation else "live",
                current=current, next=following, **score_window(current, following, weekly))


def project_morning(snapshot_day, weekly, official, market_fresh, calendars):
    """Price periods as of the next weekday, using only evidence in this snapshot."""
    review_day = snapshot_day + DAY
    while review_day.weekday() >= 5:
        review_day += DAY
    known = [row for row in official if row["published"] <= snapshot_day.isoformat()]
    projection = build_window(review_day, weekly, known, market_fresh, calendars)
    projection.update(evidence_as_of=snapshot_day.isoformat(), actionable=False)
    return projection
