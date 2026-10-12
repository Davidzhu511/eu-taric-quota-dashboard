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
    def test_new_untranslated_label_fails_build(self):
        with self.assertRaises(ValueError):translate('<span>新增漏译词汇</span>')
