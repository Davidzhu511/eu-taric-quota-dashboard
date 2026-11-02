"""Offline tests for deployment identity, hashes, and missing files."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from scripts.write_publish_manifest import TRACKED_FILES, build_manifest
from scripts.verify_live_site import verify_once

class PublishManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in TRACKED_FILES:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(("fixture:" + name).encode())
        self.manifest = build_manifest(self.root, "123", "2")
        self.responses = {"publish-manifest.json": json.dumps(self.manifest).encode()}
        self.responses.update({name: (self.root / name).read_bytes()
                               for name in TRACKED_FILES})
    def fetch(self, url):
        return self.responses[urlsplit(url).path.split("/repo/")[1]]
    def test_correct_deploy(self):
        self.assertEqual(verify_once("https://example.com/repo/", "123", "2", self.fetch),
                         len(TRACKED_FILES))
    def test_stale_deploy_rejected(self):
        with self.assertRaisesRegex(ValueError, "just-deployed"):
            verify_once("https://example.com/repo/", "124", "2", self.fetch)
    def test_mismatched_page_rejected(self):
        self.responses["uk-en.html"] = b"old-page"
        with self.assertRaisesRegex(ValueError, "uk-en.html"):
            verify_once("https://example.com/repo/", "123", "2", self.fetch)
    def test_missing_page_rejected(self):
        (self.root / "en.html").unlink()
        with self.assertRaises(FileNotFoundError):
            build_manifest(self.root, "123", "2")
    def test_missing_manifest_entry_rejected(self):
        bad = dict(self.manifest, files={k: v for k, v in self.manifest["files"].items()
                                         if k != "uk.html"})
        self.responses["publish-manifest.json"] = json.dumps(bad).encode()
        with self.assertRaisesRegex(ValueError, "missing or unexpected"):
            verify_once("https://example.com/repo/", "123", "2", self.fetch)

if __name__ == "__main__":
    unittest.main()
