import re
import unittest
from pathlib import Path
from scripts.build_english_pages import translate

ROOT=Path(__file__).resolve().parents[1]
class EnglishBuildTests(unittest.TestCase):
    def test_same_controls_and_data_paths(self):
        for filename in ['index.html','uk.html']:
            with self.subTest(filename=filename):
                zh=(ROOT/filename).read_text()
                en=translate(zh)
                self.assertIn('lang="en"',en)
                self.assertEqual(re.findall(r'\bid="([^"]+)"',zh),re.findall(r'\bid="([^"]+)"',en))
                self.assertEqual(re.findall(r'\./data/[^`"\s]+',zh),re.findall(r'\./data/[^`"\s]+',en))
                self.assertFalse(re.search('[\u4e00-\u9fff]',en))
                self.assertNotIn('、', en)
    def test_uk_english_control_labels(self):
        en = translate((ROOT/'uk.html').read_text())
        for label in [
            'Export CSV',
            'Export JSON',
            '058608 remaining',
            '058608 balance / initial volume',
            'Quarterly carryover, critical status and duty guidance',
        ]:
            with self.subTest(label=label):
                self.assertIn(label, en)
        for broken in ['CSVExport', 'JSONExport', '058608remaining', '058608Balance', 'carryover、']:
            self.assertNotIn(broken, en)

    def test_exhausted_card_badge_is_not_estimated_excess(self):
        zh = (ROOT/'index.html').read_text()
        en = translate(zh)
        self.assertIn('.quota-card.high.exhausted::before { content: "已耗尽"; }', zh)
        self.assertIn('${exhausted ? "exhausted" : ""}', zh)
        self.assertIn('.quota-card.high.exhausted::before { content: "Exhausted"; }', en)

    def test_active_blocking_notice_only_uses_active_ranges(self):
        source = (ROOT/'index.html').read_text()
        self.assertIn('const activeBlockingPeriods = (value) => {', source)
        self.assertIn('rows.flatMap((row) => activeBlockingPeriods(row.blocking_period))', source)
        self.assertNotIn('activeBlocking.map((row) => row.blocking_period)', source)

    def test_english_notice_has_clean_sentence_boundaries(self):
        en = translate((ROOT/'index.html').read_text())
        self.assertIn('Currently within the official blocking period (', en)
        self.assertIn('). Actual allocation is not yet complete.', en)
        self.assertIn('declaration acceptance. The page may therefore understate requests in transit. Estimated blended duty', en)
        self.assertNotIn('requests in transit.Estimated blended duty', en)
        self.assertNotIn('official blocking period(', en)
        self.assertNotIn('complete.  Pending', en)

    def test_new_untranslated_label_fails_build(self):
        with self.assertRaises(ValueError):translate('<span>新增漏译词汇</span>')
