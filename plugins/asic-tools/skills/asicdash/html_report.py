#!/usr/bin/env python3
"""HTML report renderer for asicdash.

Turns the report dict from asicdash.build_report() into one self-contained
HTML file: inline CSS/JS, no CDN fetches, works offline. Collapsible sections
per scope (native <details>), plugins grouped one sub-block each, a Claude
usage section (heatmap + modal + weekly chart, see usage.py), ASIC Light /
ASIC Dark themes with a persisted toggle (follows the system scheme until the
user picks one).

Stdlib only, like the scanner itself.
"""

from __future__ import annotations

import html
from collections import Counter

from usage import usage_fragment

# Display order and sentence-case labels for the four scope sections.
SECTIONS = [
    ("CLAUDE CODE — GLOBAL", "Claude Code — global"),
    ("CLAUDE CODE — PROJECT", "Claude Code — project"),
    ("CLAUDE CODE — PLUGINS", "Claude Code — plugins"),
    ("WARP", "Warp"),
]
# Sections expanded by default; the rest open only when something needs attention.
OPEN_BY_DEFAULT = {"CLAUDE CODE — GLOBAL", "CLAUDE CODE — PLUGINS"}
# Plugin children rendered as compact chips; other kinds (hooks, mcp) stay rows.
CHIP_KINDS = ("skill", "agent", "command")

# ASIC Dark palette (Captain ASIC UI rules); elevated surfaces get lighter, not darker.
_DARK_VARS = """\
  color-scheme: dark;
  --bg: #0d0a07; --surface: #1a1410; --surface-2: #251c14;
  --border: #322820; --text: #e8e0d8; --muted: #a89f93; --faint: #7d756b;
  --primary: #d4652a; --secondary: #c4843a;
  --ok: #57ab5a; --warn: #d4a72c; --err: #e5534b;
  --warn-bg: #2a2113; --err-bg: #2b1715; --chip-agent-bg: #2c2315;"""

_CSS = """\
:root {
  color-scheme: light;
  --bg: #faf6f2; --surface: #ffffff; --surface-2: #f3ece4;
  --border: #e5dbd0; --text: #1a1410; --muted: #5c5f62; --faint: #8a8d90;
  --primary: #b8491e; --secondary: #a06b2d;
  --ok: #2f7d46; --warn: #9a6700; --err: #c0362c;
  --warn-bg: #f6ecd4; --err-bg: #f6e2de; --chip-agent-bg: #f1e6d2;
}
:root[data-theme="dark"] {
@DARK@
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
@DARK@
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 ui-sans-serif, system-ui, sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 32px 24px 48px; }
header { display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; margin-bottom: 16px; }
h1 { font-size: 18px; font-weight: 500; margin: 0; }
.sub { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.sub code { font-family: ui-monospace, monospace; font-size: 12px; }
button { background: var(--surface); border: 1px solid var(--border); color: var(--text);
  border-radius: 8px; padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer;
  transition: background-color 150ms ease; }
button:hover { background: var(--surface-2); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 16px; }
.card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 16px; }
.card .label { font-size: 12px; color: var(--muted); }
.card .value { font-size: 22px; font-weight: 500; margin-top: 2px; }
.value.ok { color: var(--ok); } .value.warn { color: var(--warn); }
.value .unit { font-size: 13px; font-weight: 400; color: var(--muted); }
.banner { display: flex; align-items: center; gap: 10px; border-radius: 8px;
  padding: 10px 14px; margin-bottom: 8px; font-size: 13px; }
.banner.warn { background: var(--warn-bg); color: var(--warn); }
.banner.err { background: var(--err-bg); color: var(--err); }
.banner svg { flex: none; }
.banner .src { margin-left: auto; font-family: ui-monospace, monospace; font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 40%; }
.allok { font-size: 13px; color: var(--ok); margin: 0 0 12px; }
details.sec { background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; margin-bottom: 10px; }
summary { display: flex; align-items: center; gap: 10px; padding: 10px 16px;
  cursor: pointer; list-style: none; font-size: 14px; font-weight: 500; }
summary::-webkit-details-marker { display: none; }
.chev { color: var(--faint); flex: none; transition: transform 150ms ease; }
details[open] > summary .chev { transform: rotate(90deg); }
.meta { margin-left: auto; font-size: 12px; font-weight: 400; color: var(--muted);
  text-align: right; }
.meta .issue { color: var(--warn); }
.row { display: flex; align-items: center; gap: 10px; padding: 8px 16px;
  border-top: 1px solid var(--border); font-size: 13px; }
.kind { flex: none; font-size: 11px; padding: 2px 8px; border-radius: 6px;
  background: var(--surface-2); color: var(--muted); min-width: 64px; text-align: center; }
.name { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.detail { margin-left: auto; min-width: 0; color: var(--muted); font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tok { flex: none; font-size: 11px; color: var(--faint);
  font-family: ui-monospace, monospace; }
.dot { flex: none; width: 8px; height: 8px; border-radius: 50%; }
.dot.ok { background: var(--ok); } .dot.warn { background: var(--warn); }
.dot.bad { background: var(--err); } .dot.na { background: var(--faint); }
details.plg { margin: 0 12px 10px; border: 1px solid var(--border); border-radius: 8px; }
details.plg > summary { padding: 9px 12px; font-size: 13px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 2px 12px 12px; }
.chip { font-size: 11px; padding: 3px 9px; border-radius: 6px;
  background: var(--surface-2); color: var(--muted); }
.chip.agent { background: var(--chip-agent-bg); color: var(--secondary); }
.chip.bad { background: var(--err-bg); color: var(--err); }
.ctx { margin-top: 18px; }
.ctx .head { display: flex; justify-content: space-between; font-size: 12px;
  color: var(--muted); margin-bottom: 6px; }
.bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: var(--surface-2); }
.seg1 { background: var(--primary); } .seg2 { background: var(--secondary); }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); margin-top: 6px; }
.sw { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; }
.sw.s1 { background: var(--primary); } .sw.s2 { background: var(--secondary); }
""".replace("@DARK@", _DARK_VARS)

_ICON_CHEVRON = (
    '<svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none"'
    ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
    ' stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6l-6 6"/></svg>'
)
_ICON_ALERT = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636'
    ' 2.871h16.214a1.914 1.914 0 0 0 1.636-2.87l-8.106-13.536a1.914 1.914 0 0 0-3.274 0z"/>'
    '<path d="M12 16h.01"/></svg>'
)

# Theme toggle: follow the system scheme until the user picks one, then persist.
_JS = """\
(function () {
  var btn = document.getElementById("theme-toggle");
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem("asicdash-theme"); } catch (e) {}
  if (stored === "light" || stored === "dark") root.setAttribute("data-theme", stored);
  function current() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function label() {
    btn.textContent = current() === "dark" ? "Light mode" : "Dark mode";
  }
  btn.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("asicdash-theme", next); } catch (e) {}
    label();
  });
  label();
})();
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _plural(kind: str, n: int) -> str:
    if n == 1:
        return kind
    if kind == "memory":
        return "memories"
    return kind if kind.endswith("s") else kind + "s"


def _kind_counts(rows: list[dict]) -> str:
    counts = Counter(e["kind"] for e in rows)
    return " · ".join(f"{n} {_plural(k, n)}" for k, n in sorted(counts.items()))


def _flagged(e: dict) -> bool:
    """True when a row should force its section open and color its dot."""
    status = e["status"]
    return bool(e["attention"]) or not (status == "ok" or status.startswith("n/a"))


def _dot_class(e: dict) -> str:
    status = e["status"]
    if status.startswith("broken"):
        return "bad"
    if status.startswith(("shadowed", "unregistered")):
        return "warn"
    if status.startswith("n/a"):
        return "na"
    return "warn" if e["attention"] else "ok"


def _row(e: dict) -> str:
    """One config item as a flex row: kind badge, name, detail, tokens, status dot."""
    detail = e["desc"] or (e["status"] if e["status"].startswith("n/a") else e["source"])
    title = f"{e['kind']} · {e['scope']} · status: {e['status']} · {e['source']}"
    tok = f'<span class="tok">~{e["tokens"]} tok</span>' if e["tokens"] else ""
    return (
        f'<div class="row" title="{_esc(title)}"><span class="kind">{_esc(e["kind"])}</span>'
        f'<span class="name">{_esc(e["name"])}</span>'
        f'<span class="detail">{_esc(detail)}</span>{tok}'
        f'<span class="dot {_dot_class(e)}"></span></div>'
    )


def _chip(e: dict) -> str:
    cls = "chip bad" if _flagged(e) else ("chip agent" if e["kind"] == "agent" else "chip")
    title = f"{e['kind']} · status: {e['status']} · {e['desc'] or e['source']}"
    return f'<span class="{cls}" title="{_esc(title)}">{_esc(e["name"])}</span>'


def _plugin_block(plugin: dict, children: list[dict]) -> str:
    """One installed plugin as a nested <details>: chips for skills/agents, rows for the rest."""
    short_name = plugin["name"].split("@")[0]
    issues = sum(_flagged(e) for e in [plugin, *children])
    meta = _kind_counts(children) if children else "no components"
    note = (
        f' · <span class="issue">{issues} issue{"s" if issues != 1 else ""}</span>'
        if issues
        else " · all ok"
    )
    open_attr = " open" if issues else ""
    chips = [e for e in children if e["kind"] in CHIP_KINDS]
    rows = [e for e in children if e["kind"] not in CHIP_KINDS]
    if _flagged(plugin):
        rows.insert(0, plugin)
    parts = [
        f'<details class="plg"{open_attr}><summary>{_ICON_CHEVRON}'
        f'<span title="{_esc(plugin["name"] + " — " + plugin["desc"])}">{_esc(short_name)}</span>'
        f'<span class="meta">{meta}{note}</span></summary>'
    ]
    if chips:
        parts.append('<div class="chips">' + "".join(_chip(e) for e in chips) + "</div>")
    parts += [_row(e) for e in rows]
    parts.append("</details>")
    return "".join(parts)


def _plugins_section(rows: list[dict]) -> tuple[str, str]:
    """Body and summary-meta for the plugins section, grouped per plugin."""
    plugins = sorted((e for e in rows if e["kind"] == "plugin"), key=lambda e: e["name"].lower())
    grouped: list[str] = []
    claimed: set[int] = set()
    for p in plugins:
        scope = "plugin:" + p["name"].split("@")[0]
        children = [e for e in rows if e["scope"] == scope and e["kind"] != "plugin"]
        claimed |= {id(e) for e in [p, *children]}
        grouped.append(_plugin_block(p, children))
    # orphans: plugin-scoped entries whose plugin record is missing — still show them
    orphans = [e for e in rows if id(e) not in claimed]
    grouped += [_row(e) for e in _sorted_rows(orphans)]
    child_counts = _kind_counts([e for e in rows if e["kind"] != "plugin"])
    meta = f"{len(plugins)} {_plural('plugin', len(plugins))}"
    return "".join(grouped), meta + (f" · {child_counts}" if child_counts else "")


def _sorted_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda e: (e["kind"], e["scope"], e["name"].lower()))


def _section(key: str, label: str, rows: list[dict]) -> str:
    if key == "CLAUDE CODE — PLUGINS":
        body, meta = _plugins_section(rows)
    else:
        body = "".join(_row(e) for e in _sorted_rows(rows))
        meta = _kind_counts(rows)
    open_attr = " open" if key in OPEN_BY_DEFAULT or any(_flagged(e) for e in rows) else ""
    return (
        f'<details class="sec"{open_attr}><summary>{_ICON_CHEVRON}{_esc(label)}'
        f'<span class="meta">{meta}</span></summary>{body}</details>'
    )


def _stat_cards(summary: dict, entries: list[dict]) -> str:
    total = sum(1 for e in entries if not e["status"].startswith("n/a"))
    attention = len(summary["attention"])
    healthy = max(0, total - attention)
    ctx = summary["always_loaded_tokens"] + summary["desc_tokens"]
    cards = [
        ("items", str(total), ""),
        ("healthy", str(healthy), " ok"),
        ("attention", str(attention), " warn" if attention else ""),
        ("context per session", f'~{ctx} <span class="unit">tok</span>', ""),
    ]
    return (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value{cls}">{value}</div></div>'
            for label, value, cls in cards
        )
        + "</div>"
    )


def _banners(attention: list[dict]) -> str:
    if not attention:
        return '<p class="allok">No broken, shadowed, or unregistered items.</p>'
    out = []
    for a in attention:
        severity = "err" if a["detail"].startswith("broken") else "warn"
        out.append(
            f'<div class="banner {severity}">{_ICON_ALERT}'
            f"<span>{_esc(a['kind'])} ‘{_esc(a['name'])}’ — {_esc(a['detail'])}</span>"
            f'<span class="src">{_esc(a["source"])}</span></div>'
        )
    return "".join(out)


def _context_bar(summary: dict) -> str:
    always, desc = summary["always_loaded_tokens"], summary["desc_tokens"]
    total = always + desc
    if not total:
        return ""
    pct = round(always / total * 100)
    return (
        '<div class="ctx"><div class="head"><span>context cost per session</span>'
        f"<span>~{total} tokens</span></div>"
        f'<div class="bar"><div class="seg1" style="width:{pct}%"'
        f' title="memory and rules files: ~{always} tok"></div>'
        f'<div class="seg2" style="width:{100 - pct}%"'
        f' title="skill/agent/command descriptions: ~{desc} tok"></div></div>'
        f'<div class="legend"><span><span class="sw s1"></span>memory + rules ~{always}</span>'
        f'<span><span class="sw s2"></span>skill/agent descriptions ~{desc}'
        " (system prompt)</span></div></div>"
    )


def render_html(report: dict) -> str:
    """Render the asicdash report dict as a complete standalone HTML document.

    Args:
        report: Payload from asicdash.build_report() — project, generated
            timestamp, summary (counts, token estimates, attention list),
            entries enriched with section and attention fields, and an
            optional "usage" payload from usage.collect_usage().

    Returns:
        Full HTML document as a string, ready to write to disk.
    """
    entries = report["entries"]
    summary = report["summary"]
    sections = "".join(
        _section(key, label, [e for e in entries if e["section"] == key])
        for key, label in SECTIONS
        if any(e["section"] == key for e in entries)
    )
    u_css, u_html, u_js = ("", "", "")
    if report.get("usage"):
        u_css, u_html, u_js = usage_fragment(report["usage"], _ICON_CHEVRON)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>asicdash — {_esc(report['project'])}</title>"
        f"<style>{_CSS}{u_css}</style></head><body><main>"
        f'<header><div><h1>asicdash</h1><p class="sub"><code>{_esc(report["project"])}</code>'
        f" · scanned {_esc(report['generated'])}</p></div>"
        '<button id="theme-toggle" type="button">Dark mode</button></header>'
        f"{_stat_cards(summary, entries)}{_banners(summary['attention'])}{u_html}{sections}"
        f"{_context_bar(summary)}</main><script>{_JS}</script>"
        + (f"<script>{u_js}</script>" if u_js else "")
        + "</body></html>"
    )
