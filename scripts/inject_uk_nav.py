#!/usr/bin/env python3
"""Add a visible UK-dashboard navigation button to the deployed EU page."""

from __future__ import annotations

import sys
from pathlib import Path


STYLE_ANCHOR = "    .meta {"
LINK_ANCHOR = '''        <a class="source-link" href="https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en" target="_blank" rel="noopener noreferrer">EU TARIC 官方来源 ↗</a>'''

STYLE = '''    .hero-actions {
      position: relative;
      z-index: 1;
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
    }

    .source-link.uk-link {
      border-color: var(--primary);
      background: linear-gradient(135deg, #e1c578, #b88b34);
      color: #11120f;
      font-weight: 750;
    }

'''

LINKS = '''        <div class="hero-actions" aria-label="看板导航与数据来源">
          <a class="source-link uk-link" href="./uk.html">英国配额看板 →</a>
          <a class="source-link" href="https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en" target="_blank" rel="noopener noreferrer">EU TARIC 官方来源 ↗</a>
        </div>'''

MOBILE_ANCHOR = "      .hero-top { display: block; }"
MOBILE_STYLE = '''      .hero-actions { justify-content: flex-start; margin-top: 16px; }
      .hero-actions .source-link { margin-top: 0; }
'''


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: inject_uk_nav.py PATH_TO_INDEX_HTML")

    path = Path(sys.argv[1])
    html = path.read_text(encoding="utf-8")

    if 'href="./uk.html"' in html:
        print(f"UK navigation already present in {path}")
        return 0

    if STYLE_ANCHOR not in html or LINK_ANCHOR not in html or MOBILE_ANCHOR not in html:
        raise RuntimeError("EU page structure changed; navigation injection anchors not found")

    html = html.replace(STYLE_ANCHOR, STYLE + STYLE_ANCHOR, 1)
    html = html.replace(LINK_ANCHOR, LINKS, 1)
    html = html.replace(MOBILE_ANCHOR, MOBILE_ANCHOR + "\n" + MOBILE_STYLE, 1)
    path.write_text(html, encoding="utf-8")
    print(f"Added UK dashboard navigation to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
