import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cbam_windows as m
import update_cbam_dashboard as refresh
import ensure_cbam_research as research


def ec_table(rows, headings=("Auction week", "Date of publication", "Price (€)")):
    head = "".join(f"<th>{s}</th>" for s in headings)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def series(start, prices):
    return [dict(week_start=(start + i * m.WEEK).isoformat(), price=p, volume=100, auctions=3,
                 planned_volume=100, complete=True, eligible_estimate=True) for i, p in enumerate(prices)]


class WindowTests(unittest.TestCase):
    def test_due_date_uses_collection_slot_at_midnight_and_in_summer(self):
        for stamp, expected in (
            ("2026-11-19T00:27:00+01:00", "2026-11-18"),
            ("2027-03-30T00:27:00+02:00", "2027-03-29"),
            ("2027-01-01T00:27:00+01:00", "2026-12-31"),
            ("2026-11-19T17:29:59+00:00", "2026-11-18"),
            ("2026-11-19T17:30:00+00:00", "2026-11-19"),
        ):
            with self.subTest(stamp=stamp):
                self.assertEqual(refresh.auction_results_due_through(datetime.fromisoformat(stamp)).isoformat(), expected)

    def test_refresh_does_not_require_friday_result_on_friday_morning(self):
        days = [f"2026-11-{day}" for day in (16, 17, 19, 20)]
        rows = [dict(date=day, price=85, volume=100) for day in days[:-1]]
        plan = {"2026": {"days": dict.fromkeys(days, 100)}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "current.json"
            with patch.multiple(refresh, CURRENT=path, HISTORY_DIR=Path(temp) / "history",
                                fetch_auction_years=lambda *_: (rows, set(), True),
                                fetch_calendars=lambda *_: (plan, True), get=lambda *_: "",
                                fetch_commission=lambda *_: ([], [], True)):
                for stamp, fresh in (("2026-11-20T00:39:00+01:00", True), ("2026-11-20T19:00:00+01:00", False)):
                    with self.subTest(stamp=stamp), patch.object(refresh, "now_utc", return_value=datetime.fromisoformat(stamp)):
                        refresh.main()
                        data = json.loads(path.read_text())
                        self.assertEqual(data["procurement_window"]["market_source_verified"], fresh)
                        self.assertEqual(data["auction_analytics"]["weekly"][-1]["eligible_estimate"], fresh)
                        self.assertEqual(data["meta"]["status"], "ok" if fresh else "degraded")
                        self.assertEqual(data["morning_window"]["as_of"], "2026-11-23")

    def test_morning_projection_uses_only_published_evidence_and_expires_old_price(self):
        rows = m.official_weeks(ec_table([("W03","25 January 2027","86"),
                                          ("W04","1 February 2027","84")]))
        friday = m.project_morning(date(2027,1,29), [], rows, True, {})
        self.assertEqual(friday["as_of"], "2027-02-01")
        self.assertEqual(friday["current"]["price"], 86)
        self.assertIsNone(friday["next"])  # Monday publication was still unknown on Friday.
        self.assertFalse(friday["actionable"])
        after_publication = m.project_morning(date(2027,2,1), [], rows, True, {})
        self.assertEqual(after_publication["as_of"], "2027-02-02")
        self.assertEqual(after_publication["current"]["price"], 84)
        self.assertIsNone(after_publication["spread"])
        self.assertIsNone(after_publication["score"])

    def test_changeover_publication_and_sale_start(self):
        official = m.official_weeks(ec_table([("W03", "25 January 2027", "86.00"),
                                               ("W04", "1 February 2027", "84.00")]))
        jan = m.build_window(date(2027, 1, 31), [], official)
        self.assertEqual(jan["mode"], "simulation")
        self.assertIsNone(jan["next"])
        mon = m.build_window(date(2027, 2, 1), [], official)
        self.assertEqual((mon["mode"], mon["current"]["price"], mon["next"]["price"]), ("live", 86, 84))
        self.assertEqual(mon["next_effective_from"], "2027-02-02")
        self.assertEqual(mon["direction"], "next_cheaper")
        tue = m.build_window(date(2027, 2, 2), [], official)
        self.assertEqual(tue["current"]["price"], 84)
        self.assertIsNone(tue["next"])
        self.assertIsNone(m.build_window(date(2027, 2, 9), [], official)["current"])

    def test_holiday_explicit_and_unknown_years(self):
        quote, = m.official_weeks(ec_table([("W12", "30 March 2027", "75,25")]))
        self.assertEqual((quote["valid_from"], quote["valid_to"]), ("2027-03-31", "2027-04-05"))
        quote, = m.official_weeks(ec_table([("W16", "26 April 2027", "80")]))
        self.assertEqual(quote["valid_to"], "2027-05-03")
        self.assertFalse(m.official_weeks(ec_table([("W10", "13 March 2028", "90")])))
        headings = ("Valid from", "Valid until", "Published", "Price")
        quote, = m.official_weeks(ec_table([("2028-03-14","2028-03-20","2028-03-13","90")], headings))
        self.assertEqual(quote["valid_to"], "2028-03-20")
        self.assertFalse(m.official_weeks(ec_table([("Q4 2026","4 January 2027","86.00")])))
        with self.assertRaises(ValueError):
            m.official_weeks(ec_table([("W03","25 January 2027","83"),("W03","25 January 2027","84")]))

    def test_score_rank_ties_missing_history_and_bounds(self):
        weeks = series(date(2026, 6, 1), [75]*13 + [80]*13 + [999])
        p = dict(price=80, formation_week=weeks[-1]["week_start"])
        r = m.score_window(p, dict(price=82), weeks)
        self.assertEqual((r["spread_points"], r["history_points"], r["score"]), (60,10,70))
        self.assertEqual(r["impact_per_1000"], 2000)
        weeks[3]["complete"] = False
        r = m.score_window(p, dict(price=72), weeks)
        self.assertEqual((r["spread_points"], r["score"], r["direction"]), (0,None,"next_cheaper"))
        self.assertIsNone(m.score_window(None,None,weeks)["score"])

    def test_partial_complete_cancelled_missing_and_no_plan(self):
        dates = [f"2027-02-0{x}" for x in (1,2,3,4)]
        plan = {"2027":{"days":dict(zip(dates, [15,15,15,15]))}}
        a = [dict(date=d, volume=15) for d in dates[:3]]
        w = dict(week_start=dates[0], volume=45, auctions=3)
        def mark(plan, cancelled, day):
            m.mark_weeks([w], a, plan, cancelled, day)
            return (w["eligible_estimate"], w["complete"])
        self.assertEqual(mark(plan,set(),dates[2]),(True,False))
        self.assertEqual(mark(plan,set(),dates[3]),(False,False))
        self.assertEqual(mark(plan,{dates[3]},dates[3]),(True,True))
        self.assertEqual(mark({},set(),dates[3]),(False,False))
        plan["2027"]["days"][dates[-1]] = 100
        self.assertEqual(mark(plan,set(),dates[2]),(False,False))

    def test_no_auction_week_uses_last_full_auction_week(self):
        official = m.official_weeks(ec_table([("W04","1 February 2027","80")]))
        weeks = series(date(2027,1,25), [80])
        target = date(2027,2,1)
        cal = {"2027":{"days":{(target+i*m.DAY).isoformat():0 for i in range(5)}}}
        w = m.build_window(date(2027,2,5), weeks, official, True, cal)
        self.assertEqual(w["next"]["kind"],"no_auctions_estimate")
        self.assertEqual(w["spread"],0)
        self.assertIsNone(m.build_window(date(2027,2,5), weeks, official, False, cal)["next"])

    def test_calendar_layout_including_indicative_autumn_volumes(self):
        book = Workbook()
        sheet = book.active
        sheet.title = "Details_EUA"
        sheet.append(["Date",datetime(2027,9,1),datetime(2027,9,2)])
        sheet.append(["Consolidated Volume *",None,3133500])
        blob = BytesIO()
        book.save(blob)
        self.assertEqual(m.calendar_days(blob.getvalue(),2027), {"2027-09-01":0,"2027-09-02":3133500})

    def test_capture_q4_after_rollover_preserve_confirmed_prices(self):
        page = ec_table([("Q4 2026","4 January 2027","85.24")],
                        ("Quarter of application","Date of publication","Price (€)"))
        previous = {"official_cbam_prices":[dict(year=2026,quarter=q,price=75.) for q in (1,2,3)]}
        with patch.object(refresh,"get",return_value=page):
            q, weekly, _ = refresh.fetch_commission(date(2027,1,5),previous,[])
        self.assertEqual([r["price"] for r in q],[75.,75.,75.,85.24])
        self.assertEqual(weekly,[])

    def test_cross_year_sources_and_stale_fallback(self):
        old = dict(date="2026-12-15",price=80,volume=12)
        new = dict(date="2027-01-07",price=81,volume=12)
        with patch.object(refresh,"get",side_effect=[b"old",b"new"]), patch.object(
                refresh,"parse_auction_xlsx",side_effect=[[old],[new]]):
            rows, _, fresh = refresh.fetch_auction_years(date(2027,1,8),{"auctions":[old]},[])
        self.assertTrue(fresh)
        self.assertEqual(rows,[old,new])
        errors = []
        with patch.object(refresh,"get",side_effect=refresh.requests.Timeout("timeout")):
            rows, _, fresh = refresh.fetch_auction_years(date(2027,1,8),{"auctions":[old,new]},errors)
        self.assertEqual(rows,[old,new])
        self.assertFalse(fresh)
        self.assertTrue(errors)

    def test_research_note_never_becomes_a_score(self):
        now = datetime(2027,2,2,tzinfo=timezone.utc)
        data = dict(procurement_window={},meta=dict(data_date="2027-02-01",checked_at=now.isoformat()))
        note = dict(summary="Fact",sources=["https://example.com"],overlay_score=None,meta=dict(
            public_data_date="2027-02-01",updated_at=now.isoformat(),status="research_note"))
        self.assertTrue(research.valid_same_day_research(note,data,now))
        note["overlay_score"] = 30
        self.assertFalse(research.valid_same_day_research(note,data,now))
        self.assertIsNone(research.create_fallback(data,now)["overlay_score"])
