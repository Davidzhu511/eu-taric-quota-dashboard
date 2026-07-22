#!/usr/bin/env python3
"""Inject shared navigation and persistent theme controls into both dashboards."""

from __future__ import annotations

import sys
from pathlib import Path


HEAD_ASSETS = '''  <script>
    (() => {
      try {
        const saved = localStorage.getItem("quota-dashboard-theme");
        document.documentElement.dataset.theme = saved || "black-gold";
      } catch (_) {
        document.documentElement.dataset.theme = "black-gold";
      }
    })();
  </script>
  <link rel="stylesheet" href="./shared-ui.css">
'''

BODY_ASSET = '  <script src="./shared-ui.js"></script>\n'

SHARED_CSS = r''':root {
  --ui-bg: #0b0c0b;
  --ui-surface: #2a2b27;
  --ui-surface-deep: #181916;
  --ui-text: #f3ecd9;
  --ui-muted: #aaa99f;
  --ui-border: rgba(211, 177, 95, 0.28);
  --ui-accent: #d3b15f;
  --ui-accent-strong: #b88b34;
  --ui-accent-soft: rgba(211, 177, 95, 0.14);
  --ui-secondary-soft: rgba(119, 121, 114, 0.18);
  --ui-title-start: #f5e5b3;
  --ui-title-end: #b88b34;
}

html[data-theme="black-gold"] {
  color-scheme: dark;
}

html[data-theme="elephant-grey"] {
  color-scheme: dark;
  --ui-bg: #171918;
  --ui-surface: #3a3d3a;
  --ui-surface-deep: #252825;
  --ui-text: #f0f0e9;
  --ui-muted: #b8bbb5;
  --ui-border: rgba(194, 198, 190, 0.25);
  --ui-accent: #c7b37a;
  --ui-accent-strong: #93815a;
  --ui-accent-soft: rgba(199, 179, 122, 0.14);
  --ui-secondary-soft: rgba(166, 171, 163, 0.17);
  --ui-title-start: #f2ead4;
  --ui-title-end: #a79462;
}

html[data-theme="steel-blue"] {
  color-scheme: dark;
  --ui-bg: #09131c;
  --ui-surface: #1d3344;
  --ui-surface-deep: #102331;
  --ui-text: #edf5fa;
  --ui-muted: #a9bdca;
  --ui-border: rgba(115, 174, 211, 0.30);
  --ui-accent: #75b5d9;
  --ui-accent-strong: #3f83ad;
  --ui-accent-soft: rgba(117, 181, 217, 0.15);
  --ui-secondary-soft: rgba(78, 129, 158, 0.18);
  --ui-title-start: #d9f0fb;
  --ui-title-end: #4f9cc8;
}

html[data-theme="ivory"] {
  color-scheme: light;
  --ui-bg: #f1ede3;
  --ui-surface: #fffdf8;
  --ui-surface-deep: #e7e0d2;
  --ui-text: #28251f;
  --ui-muted: #6e685e;
  --ui-border: rgba(125, 99, 46, 0.25);
  --ui-accent: #9a7228;
  --ui-accent-strong: #76551b;
  --ui-accent-soft: rgba(154, 114, 40, 0.12);
  --ui-secondary-soft: rgba(112, 108, 98, 0.12);
  --ui-title-start: #795718;
  --ui-title-end: #b18431;
}

html[data-theme] {
  --bg: var(--ui-bg);
  --surface: var(--ui-surface);
  --surface-solid: var(--ui-surface);
  --surface-deep: var(--ui-surface-deep);
  --deep: var(--ui-surface-deep);
  --text: var(--ui-text);
  --muted: var(--ui-muted);
  --border: var(--ui-border);
  --primary: var(--ui-accent);
  --primary-soft: var(--ui-accent-soft);
  --accent: var(--ui-accent-strong);
  --accent-soft: var(--ui-secondary-soft);
  --success: var(--ui-accent);
  --success-soft: var(--ui-accent-soft);
  --gold: var(--ui-accent);
  --gold-deep: var(--ui-accent-strong);
  --grey: var(--ui-muted);
  --elephant: var(--ui-muted);
}

html[data-theme] body {
  background:
    radial-gradient(circle at 7% 0%, var(--ui-accent-soft), transparent 30%),
    radial-gradient(circle at 94% 4%, var(--ui-secondary-soft), transparent 28%),
    var(--ui-bg) !important;
  color: var(--ui-text) !important;
  transition: background 180ms ease, color 180ms ease;
}

html[data-theme] .hero,
html[data-theme] .toolbar,
html[data-theme] .stat,
html[data-theme] .quota-card,
html[data-theme] .card {
  border-color: var(--ui-border) !important;
  background: linear-gradient(145deg, var(--ui-surface), var(--ui-surface-deep)) !important;
}

html[data-theme] h1,
html[data-theme] .title {
  background: linear-gradient(92deg, var(--ui-title-start), var(--ui-accent), var(--ui-title-end)) !important;
  -webkit-background-clip: text !important;
  background-clip: text !important;
  color: transparent !important;
}

html[data-theme="ivory"] .source-link,
html[data-theme="ivory"] .button,
html[data-theme="ivory"] .control,
html[data-theme="ivory"] .pill,
html[data-theme="ivory"] .dashboard-source,
html[data-theme="ivory"] .theme-control,
html[data-theme="ivory"] .dashboard-switch {
  box-shadow: 0 6px 18px rgba(82, 65, 31, 0.10);
}

.dashboard-actions {
  position: relative;
  z-index: 2;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 9px;
  max-width: 760px;
}

.dashboard-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 42px;
  padding: 4px;
  border: 1px solid var(--ui-border);
  border-radius: 13px;
  background: var(--ui-surface-deep);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.18);
}

.dashboard-tab,
.dashboard-source,
.theme-control {
  min-height: 34px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: var(--ui-text);
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
}

.dashboard-tab {
  display: inline-flex;
  align-items: center;
  padding: 7px 11px;
  color: var(--ui-muted);
}

.dashboard-tab:hover,
.dashboard-source:hover {
  border-color: var(--ui-accent);
  color: var(--ui-accent);
}

.dashboard-tab.active {
  border-color: var(--ui-accent);
  background: linear-gradient(135deg, var(--ui-accent), var(--ui-accent-strong));
  color: #11120f;
  box-shadow: 0 6px 16px var(--ui-accent-soft);
}

.dashboard-source {
  display: inline-flex;
  align-items: center;
  min-height: 42px;
  padding: 9px 12px;
  border-color: var(--ui-border);
  background: var(--ui-surface);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16);
}

.theme-control {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 42px;
  padding: 5px 7px 5px 11px;
  border-color: var(--ui-border);
  background: var(--ui-surface);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16);
}

.theme-control span {
  color: var(--ui-muted);
  white-space: nowrap;
}

.theme-control select {
  min-height: 30px;
  border: 0;
  border-radius: 7px;
  outline: none;
  background: var(--ui-surface-deep);
  color: var(--ui-text);
  padding: 4px 25px 4px 8px;
  font: inherit;
  cursor: pointer;
}

@media (max-width: 760px) {
  .dashboard-actions {
    width: 100%;
    max-width: none;
    justify-content: flex-start;
    margin-top: 16px;
  }

  .dashboard-switch {
    order: 1;
  }

  .theme-control {
    order: 2;
  }

  .dashboard-source {
    order: 3;
  }
}

@media (max-width: 430px) {
  .dashboard-actions,
  .dashboard-switch {
    width: 100%;
  }

  .dashboard-tab {
    flex: 1;
    justify-content: center;
  }

  .theme-control,
  .dashboard-source {
    width: 100%;
  }

  .theme-control select {
    flex: 1;
  }
}
'''

SHARED_JS = r'''(() => {
  const THEME_KEY = "quota-dashboard-theme";
  const THEMES = new Set(["black-gold", "elephant-grey", "steel-blue", "ivory"]);
  const isUk = /(?:^|\/)uk\.html$/.test(window.location.pathname);
  const heroTop = document.querySelector(".hero-top");
  if (!heroTop) return;

  const existingRight = heroTop.querySelector(".dashboard-actions") || heroTop.lastElementChild;
  const actions = document.createElement("div");
  actions.className = "dashboard-actions";
  actions.setAttribute("aria-label", "看板切换、官方来源与配色");

  const euActive = isUk ? "" : " active";
  const ukActive = isUk ? " active" : "";
  const sourceHref = isUk
    ? "https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026"
    : "https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp?Lang=en";
  const sourceText = isUk ? "英国立法文件 ↗" : "EU TARIC官方来源 ↗";
  const sourceId = isUk ? ' id="law-link"' : "";

  actions.innerHTML = `
    <nav class="dashboard-switch" aria-label="地区看板切换">
      <a class="dashboard-tab${euActive}" href="./">欧盟看板</a>
      <a class="dashboard-tab${ukActive}" href="./uk.html">英国看板</a>
    </nav>
    <a class="dashboard-source"${sourceId} href="${sourceHref}" target="_blank" rel="noopener noreferrer">${sourceText}</a>
    <label class="theme-control">
      <span>配色</span>
      <select id="dashboard-theme" aria-label="选择看板配色">
        <option value="black-gold">黑金</option>
        <option value="elephant-grey">大象灰</option>
        <option value="steel-blue">钢铁蓝</option>
        <option value="ivory">象牙白</option>
      </select>
    </label>`;

  if (existingRight && !existingRight.matches("h1, .title") && existingRight !== heroTop.firstElementChild) {
    existingRight.replaceWith(actions);
  } else {
    heroTop.append(actions);
  }

  const selector = actions.querySelector("#dashboard-theme");
  let current = document.documentElement.dataset.theme || "black-gold";
  if (!THEMES.has(current)) current = "black-gold";
  selector.value = current;

  selector.addEventListener("change", () => {
    const selected = THEMES.has(selector.value) ? selector.value : "black-gold";
    document.documentElement.dataset.theme = selected;
    try {
      localStorage.setItem(THEME_KEY, selected);
    } catch (_) {
      // Storage can be unavailable in private or restricted browsing modes.
    }
  });
})();
'''


def inject_assets(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    if 'href="./shared-ui.css"' not in html:
        if "</head>" not in html:
            raise RuntimeError(f"{path}: missing </head>")
        html = html.replace("</head>", HEAD_ASSETS + "</head>", 1)
    if 'src="./shared-ui.js"' not in html:
        if "</body>" not in html:
            raise RuntimeError(f"{path}: missing </body>")
        html = html.replace("</body>", BODY_ASSET + "</body>", 1)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: inject_uk_nav.py PATH_TO_DEPLOYED_INDEX_HTML")

    index_path = Path(sys.argv[1])
    site_dir = index_path.parent
    uk_path = site_dir / "uk.html"
    if not index_path.exists() or not uk_path.exists():
        raise RuntimeError("both deployed index.html and uk.html must exist before UI injection")

    inject_assets(index_path)
    inject_assets(uk_path)
    (site_dir / "shared-ui.css").write_text(SHARED_CSS + "\n", encoding="utf-8")
    (site_dir / "shared-ui.js").write_text(SHARED_JS + "\n", encoding="utf-8")
    print("Unified EU/UK navigation and installed four persistent themes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
