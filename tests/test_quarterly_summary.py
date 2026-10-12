import unittest
from scripts.build_quarterly_summary import summarize

class QuarterlyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.period='01-10-2026 - 31-12-2026'
        self.eu={'meta':{'validity_period':self.period}}
        self.item={'code':'099600','origin':'Other countries','validity_period':self.period,'balance_kg':0,'exhaustion_date':'01-10-2026','last_import_date':'01-10-2026','last_allocation_date':'05-10-2026','allocated_percentage':18.624}
    def snapshot(self,item,day='05'):
        return ('2026-10-'+day+'.json',{'meta':{'official_update_date':'2026-10-'+day},'items':[item]})
    def test_zero_latest_does_not_erase_historical_allocation(self):
        result=summarize(self.eu,[self.snapshot(self.item),self.snapshot(dict(self.item,allocated_percentage=0),'07')],{})['eu'][0]
        self.assertEqual(result['weighted_duty_pct'],40.688)
        self.assertEqual(result['allocation_date'],'05-10-2026')
    def test_old_period_stale_or_missing_allocation_not_used(self):
        for change in [{'validity_period':'01-07-2026 - 30-09-2026'},{'stale':True},{'error':'timeout'},{'allocated_percentage':None},{'last_import_date':'02-10-2026'},{'balance_kg':None}]:
            with self.subTest(change=change):
                result=summarize(self.eu,[self.snapshot(dict(self.item,**change))],{})['eu'][0]
                self.assertIsNone(result['weighted_duty_pct'])
    def test_conflicting_ratios_require_review(self):
        result=summarize(self.eu,[self.snapshot(self.item),self.snapshot(dict(self.item,allocated_percentage=19),'06')],{})['eu'][0]
        self.assertEqual(result['status'],'conflicting_evidence')
        self.assertIsNone(result['weighted_duty_pct'])
    def test_uk_fill_rate_is_not_allocation(self):
        result=summarize(self.eu,[],{'items':[{'code':'058608','fill_rate':23,'balance':100,'validity_start_date':'2026-10-01'}]})['uk'][0]
        self.assertIsNone(result['weighted_duty_pct'])
    def test_quarter_switch_clears_previous_evidence(self):
        result=summarize({'meta':{'validity_period':'01-01-2027 - 31-03-2027'}},[self.snapshot(self.item)],{})['eu'][0]
        self.assertIsNone(result['allocation_pct'])
