"""Verify GitHub Pages is serving exactly the just-deployed build."""
import hashlib
import json
import os
import sys
import time
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from scripts.write_publish_manifest import TRACKED_FILES

DEFAULT_URL = "https://davidzhu511.github.io/eu-taric-quota-dashboard/"

def make_url(base_url: str, path: str, run_id: str, attempt: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("HTTPS site URL required")
    return urlunsplit((parsed.scheme, parsed.netloc,
                       parsed.path.rstrip("/") + "/" + quote(path),
                       f"deploy={run_id}-{attempt}", ""))

def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"Cache-Control": "no-cache",
                                "User-Agent": "quota-dashboard-deploy-check/1.0"})
    with urlopen(req, timeout=15) as response:
        return response.read()

def verify_once(base_url: str, run_id: str, attempt: str, fetch=fetch_bytes) -> int:
    manifest = json.loads(fetch(make_url(base_url, "publish-manifest.json", run_id, attempt)).decode("utf-8"))
    if (manifest.get("schema") != 1 or str(manifest.get("run_id")) != str(run_id)
            or str(manifest.get("attempt")) != str(attempt)):
        raise ValueError("Pages manifest is not for the just-deployed run")
    files = manifest.get("files", {})
    if set(files) != set(TRACKED_FILES):
        raise ValueError("Pages manifest missing or unexpected critical files")
    for name in TRACKED_FILES:
        raw = fetch(make_url(base_url, name, run_id, attempt))
        if (hashlib.sha256(raw).hexdigest() != files[name]["sha256"]
                or len(raw) != files[name]["bytes"]):
            raise ValueError(f"Published file mismatch: {name}")
    return len(files)

def main():
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if not run_id or not attempt:
        sys.exit("GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT required")
    base = os.environ.get("DASHBOARD_SITE_URL", DEFAULT_URL)
    for trial in range(1, 7):
        try:
            verified = verify_once(base, run_id, attempt)
            print(f"Pages verified: run={run_id} attempt={attempt} paths={verified}")
            return
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Pages not verified ({trial}/6): {exc}", flush=True)
            if trial == 6:
                sys.exit(1)
            time.sleep(12)

if __name__ == "__main__":
    main()
