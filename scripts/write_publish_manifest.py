"""Fingerprint the static bundle uploaded to GitHub Pages."""
import hashlib
import json
import os
from pathlib import Path

TRACKED_FILES = (
    "index.html", "en.html", "uk.html", "uk-en.html",
    "data/current.json", "data/uk/current.json", "data/quarterly-summary.json",
    "cbam/index.html", "cbam/data/current.json", "cbam/data/research.json",
)

def build_manifest(site: Path, run_id: str, attempt: str) -> dict:
    if not str(run_id).strip() or not str(attempt).strip():
        raise ValueError("run ID and attempt required")
    entries = {}
    for name in TRACKED_FILES:
        p = site / name
        if not p.is_file():
            raise FileNotFoundError(f"site bundle missing {name}")
        data = p.read_bytes()
        entries[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return {"schema": 1, "run_id": str(run_id), "attempt": str(attempt), "files": entries}

def main():
    site = Path(os.environ.get("SITE_DIRECTORY", "_site"))
    manifest = build_manifest(site, os.environ.get("GITHUB_RUN_ID", "local"),
                              os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    (site / "publish-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Publish manifest: {len(manifest['files'])} critical files fingerprinted")

if __name__ == "__main__":
    main()
