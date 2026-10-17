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

    def test_new_untranslated_label_fails_build(self):
        with self.assertRaises(ValueError):translate('<span>新增漏译词汇</span>')
