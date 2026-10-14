"""Claude usage collector + HTML fragment for the asicdash report.

Aggregates per-day activity from local Claude Code session transcripts
(~/.claude/projects/**/*.jsonl). Every transcript here is a Claude Code
session; the entrypoint field only records how Code was launched, which is
the one split the local data can honestly make:

  terminal — launched from the CLI (entrypoint "cli")
  desktop  — launched from the Claude desktop app (entrypoint "claude-desktop")
  chat     — claude.ai web; leaves no local transcript, always shown as
             "no local data" rather than silently omitted

Renders a GitHub-style contribution heatmap (cell color = dominant surface,
intensity = output-token quartile), a per-day breakdown modal, and a weekly
stacked bar chart. Theme-aware via the same CSS-variable mechanism as
html_report.py (ASIC light/dark). Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

SURFACES = ("terminal", "desktop")  # surfaces with local data; chat is rendered as n/a
WINDOW_DAYS = 371  # 53 weeks, matching the heatmap span


def surface_of(entrypoint: str) -> str:
    """Map a transcript entrypoint value onto a dashboard surface."""
    return "desktop" if "desktop" in entrypoint else "terminal"


def _scan_file(path: Path, by_day: dict, cutoff: datetime) -> None:
    """Fold one session transcript into the by_day aggregate.

    The entrypoint can appear on any line, so events are buffered and
    assigned to a surface once the whole file is read.
    """
    entrypoint = ""
    events: list[tuple[str, int, int]] = []  # (local date iso, out_tok, in_tok)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        if not entrypoint and d.get("entrypoint"):
            entrypoint = str(d["entrypoint"])
        msg = d.get("message")
        if d.get("type") != "assistant" or not isinstance(msg, dict):
            continue
        usage = msg.get("usage") or {}
        ts = d.get("timestamp", "")
        try:
            when = datetime.fromisoformat(ts).astimezone()
        except ValueError:
            continue
        if when < cutoff:
            continue
        out = int(usage.get("output_tokens") or 0)
        inp = int(usage.get("input_tokens") or 0)
        events.append((when.date().isoformat(), out, inp))
    if not events:
        return
    surface = surface_of(entrypoint)
    sid = path.stem
    for date_iso, out, inp in events:
        day = by_day.setdefault(date_iso, {})
        agg = day.setdefault(surface, {"out": 0, "inp": 0, "msgs": 0, "sids": set()})
        agg["out"] += out
        agg["inp"] += inp
        agg["msgs"] += 1
        agg["sids"].add(sid)


def collect_usage() -> dict:
    """Aggregate per-day, per-surface Claude usage from local transcripts.

    Returns:
        Dict with "today" (local ISO date), "days" (date -> surface ->
        out/inp/msgs/sessions), and "totals" (out tokens, active days,
        distinct sessions) covering the last 53 weeks.
    """
    cutoff = datetime.now().astimezone() - timedelta(days=WINDOW_DAYS)
    by_day: dict[str, dict] = {}
    root = Path.home() / ".claude" / "projects"
    if root.is_dir():
        for f in sorted(root.glob("*/*.jsonl")):
            _scan_file(f, by_day, cutoff)
    all_sids: set[str] = set()
    total_out = 0
    total_inp = 0
    days: dict[str, dict] = {}
    for date_iso, surfaces in sorted(by_day.items()):
        days[date_iso] = {}
        for surface, agg in surfaces.items():
            all_sids |= agg["sids"]
            total_out += agg["out"]
            total_inp += agg["inp"]
            days[date_iso][surface] = {
                "out": agg["out"],
                "inp": agg["inp"],
                "msgs": agg["msgs"],
                "sessions": len(agg["sids"]),
            }
    # Token totals over trailing windows. ISO date strings sort lexicographically, so
    # `date_iso >= bound` is a valid date filter without parsing; "" includes everything.
    today = datetime.now().astimezone().date()
    bounds = {
        "today": today.isoformat(),
        "d7": (today - timedelta(days=6)).isoformat(),
        "d30": (today - timedelta(days=29)).isoformat(),
        "all": "",
    }
    periods: dict[str, dict] = {}
    for key, since in bounds.items():
        out = inp = 0
        for date_iso, surfaces in days.items():
            if date_iso >= since:
                for agg in surfaces.values():
                    out += agg["out"]
                    inp += agg["inp"]
        periods[key] = {"out": out, "inp": inp}
    return {
        "today": today.isoformat(),
        "days": days,
        "totals": {
            "out": total_out,
            "inp": total_inp,
            "active_days": len(days),
            "sessions": len(all_sids),
            "periods": periods,
        },
    }


# ---------------------------------------------------------------------------
# HTML fragment


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{round(n / 1_000)}k"
    return str(n)


# Heatmap ramps per surface, 1 (faint) .. 4 (strong); chat appears in the
# legend/modal only. Dark stops invert so brighter = more activity.
_LIGHT_VARS = """\
  --u-terminal-1: #9fe1cb; --u-terminal-2: #5dcaa5; --u-terminal-3: #1d9e75; --u-terminal-4: #0f6e56;
  --u-desktop-1: #f5c4b3; --u-desktop-2: #f0997b; --u-desktop-3: #d85a30; --u-desktop-4: #993c1d;
  --u-chat-1: #cecbf6; --u-chat-2: #afa9ec; --u-chat-3: #7f77dd; --u-chat-4: #534ab7;"""

_DARK_VARS = """\
  --u-terminal-1: #085041; --u-terminal-2: #0f6e56; --u-terminal-3: #1d9e75; --u-terminal-4: #5dcaa5;
  --u-desktop-1: #712b13; --u-desktop-2: #993c1d; --u-desktop-3: #d85a30; --u-desktop-4: #f0997b;
  --u-chat-1: #3c3489; --u-chat-2: #534ab7; --u-chat-3: #7f77dd; --u-chat-4: #afa9ec;"""

_CELL_RULES = "".join(
    f".u-{s}-{i} {{ background: var(--u-{s}-{i}); }}\n"
    for s in ("terminal", "desktop", "chat")
    for i in range(1, 5)
)

USAGE_CSS = (
    ":root {\n" + _LIGHT_VARS + "\n}\n"
    ':root[data-theme="dark"] {\n' + _DARK_VARS + "\n}\n"
    "@media (prefers-color-scheme: dark) {\n"
    '  :root:not([data-theme="light"]) {\n'
    + _DARK_VARS
    + "\n  }\n}\n"
    + """\
.u-wrap { padding: 4px 16px 14px; border-top: 1px solid var(--border); position: relative; }
.u-tot { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0 14px; }
.u-tot-c { border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; }
.u-tot-l { font-size: 11px; color: var(--muted); }
.u-tot-v { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.4; }
.u-tot-u { font-size: 11px; font-weight: 400; color: var(--muted); }
.u-tot-s { font-size: 11px; color: var(--faint); font-variant-numeric: tabular-nums; }
.u-tip { position: absolute; display: none; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; padding: 7px 10px; font-size: 12px;
  line-height: 1.5; pointer-events: none; z-index: 5; white-space: nowrap; }
.u-tip .t-date { font-weight: 500; }
.u-tip .t-row { display: flex; align-items: center; gap: 6px; color: var(--muted); }
.u-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--muted);
  margin: 10px 0 12px; }
.u-sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px;
  margin-right: 5px; vertical-align: -1px; }
.u-legend .na { color: var(--faint); }
.u-months { position: relative; height: 14px; font-size: 11px; color: var(--faint);
  margin-left: 30px; }
.u-months span { position: absolute; top: 0; }
.u-hm { display: flex; gap: 3px; }
.u-dows { display: flex; flex-direction: column; gap: 3px; width: 27px; font-size: 10px;
  color: var(--faint); }
.u-dows span { height: 12px; line-height: 12px; }
.u-grid { display: flex; gap: 3px; }
.u-col { display: flex; flex-direction: column; gap: 3px; }
.u-cell { width: 12px; height: 12px; border-radius: 2px; background: var(--surface-2);
  flex: none; }
.u-cell[role="button"] { cursor: pointer; }
.u-cell[role="button"]:hover { outline: 1px solid var(--muted); outline-offset: 1px; }
.u-foot { display: flex; justify-content: space-between; align-items: center; font-size: 12px;
  color: var(--muted); margin-top: 8px; }
.u-scale { display: flex; gap: 3px; align-items: center; }
.u-chart-title { font-size: 12px; color: var(--muted); margin: 16px 0 6px; }
.u-chart { display: flex; gap: 6px; align-items: flex-end; height: 110px; }
.u-bar { flex: 1; display: flex; flex-direction: column-reverse; gap: 1px; min-width: 0; }
.u-seg { border-radius: 2px; min-height: 1px; }
.u-blabels { display: flex; gap: 6px; font-size: 10px; color: var(--faint); margin-top: 4px; }
.u-blabels span { flex: 1; text-align: center; white-space: nowrap; overflow: hidden; }
.u-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); display: none;
  align-items: center; justify-content: center; z-index: 10; }
.u-overlay.show { display: flex; }
.u-modal { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 16px 20px; min-width: 320px; max-width: 90vw; }
.u-m-head { display: flex; justify-content: space-between; align-items: center; gap: 16px;
  font-weight: 500; margin-bottom: 2px; }
.u-m-sub { font-size: 12px; color: var(--muted); margin: 0 0 10px; }
.u-m-row { display: flex; align-items: center; gap: 8px; padding: 7px 0;
  border-top: 1px solid var(--border); font-size: 13px; }
.u-m-row .val { margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; }
.u-m-row.na { color: var(--faint); }
"""
    # Cell-color rules LAST: `.u-{surface}-{level}` and `.u-cell` are equal-specificity, so
    # the later rule wins. Placed after the `.u-cell` empty background, the colors paint
    # active cells (and the less→more scale swatches); otherwise `.u-cell`'s background
    # overrode every color and active days rendered blank.
    + _CELL_RULES
)

USAGE_JS = """\
(function () {
  var data = JSON.parse(document.getElementById("u-data").textContent);
  var SURF = [["terminal", "Terminal"], ["desktop", "Desktop"]];
  var MN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function fmt(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return Math.round(n / 1e3) + "k";
    return String(n);
  }
  function pad(n) { return n < 10 ? "0" + n : String(n); }
  function iso(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function addDays(d, n) { var x = new Date(d); x.setDate(x.getDate() + n); return x; }
  function dayOut(day) {
    var s = 0;
    SURF.forEach(function (c) { if (day[c[0]]) s += day[c[0]].out; });
    return s;
  }
  var end = new Date(data.today + "T00:00:00");
  var start = addDays(end, -(end.getDay() + 52 * 7));
  var max = 0;
  Object.keys(data.days).forEach(function (k) {
    var t = dayOut(data.days[k]);
    if (t > max) max = t;
  });

  var overlay = document.getElementById("u-overlay");
  function openModal(k, day) {
    var d = new Date(k + "T00:00:00");
    document.getElementById("u-m-date").textContent = d.toLocaleDateString(undefined,
      { weekday: "long", year: "numeric", month: "long", day: "numeric" });
    var sessions = 0;
    SURF.forEach(function (c) { if (day[c[0]]) sessions += day[c[0]].sessions; });
    document.getElementById("u-m-sub").textContent =
      fmt(dayOut(day)) + " output tokens \\u00b7 " + sessions +
      " session" + (sessions === 1 ? "" : "s");
    var rows = "";
    SURF.forEach(function (c) {
      var v = day[c[0]];
      rows += '<div class="u-m-row"><span class="u-sw u-' + c[0] + '-3"></span>' + c[1] +
        '<span class="val">' + (v
          ? fmt(v.out) + " out \\u00b7 " + fmt(v.inp) + " in \\u00b7 " + v.sessions +
            " session" + (v.sessions === 1 ? "" : "s")
          : "\\u2014") + "</span></div>";
    });
    rows += '<div class="u-m-row na"><span class="u-sw u-chat-3"></span>Chat' +
      '<span class="val">no local data (claude.ai)</span></div>';
    document.getElementById("u-m-rows").innerHTML = rows;
    overlay.classList.add("show");
  }
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) overlay.classList.remove("show");
  });
  document.getElementById("u-m-close").addEventListener("click", function () {
    overlay.classList.remove("show");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") overlay.classList.remove("show");
  });

  var tip = document.getElementById("u-tip");
  var wrap = tip.parentNode;
  function showTip(cell, k, day, t) {
    var sessions = 0, rows = "";
    SURF.forEach(function (c) {
      var v = day[c[0]];
      if (!v) return;
      sessions += v.sessions;
      rows += '<div class="t-row"><span class="u-sw u-' + c[0] + '-3"></span>' + c[1] + " " +
        Math.round(v.out / t * 100) + "% \\u00b7 " + fmt(v.out) + " tok \\u00b7 " + v.sessions +
        " session" + (v.sessions === 1 ? "" : "s") + "</div>";
    });
    tip.innerHTML = '<div class="t-date">' +
      new Date(k + "T00:00:00").toLocaleDateString(undefined,
        { weekday: "short", month: "short", day: "numeric" }) +
      " \\u2014 " + fmt(t) + " tok \\u00b7 " + sessions +
      " session" + (sessions === 1 ? "" : "s") + "</div>" + rows;
    tip.style.display = "block";
    var cr = cell.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
    var left = cr.left - wr.left + 16;
    if (left + tip.offsetWidth > wr.width - 8) left = cr.left - wr.left - tip.offsetWidth - 6;
    var top = cr.top - wr.top - tip.offsetHeight - 6;
    if (top < 0) top = cr.top - wr.top + 18;
    tip.style.left = Math.max(0, left) + "px";
    tip.style.top = top + "px";
  }
  function hideTip() { tip.style.display = "none"; }

  var grid = document.getElementById("u-grid");
  var months = document.getElementById("u-months");
  var lastMonth = -1;
  for (var w = 0; w < 53; w++) {
    var wd = addDays(start, w * 7);
    if (wd.getMonth() !== lastMonth && wd.getDate() <= 14) {
      var lbl = document.createElement("span");
      lbl.textContent = MN[wd.getMonth()];
      lbl.style.left = w * 15 + "px";
      months.appendChild(lbl);
      lastMonth = wd.getMonth();
    }
    var col = document.createElement("div");
    col.className = "u-col";
    for (var r = 0; r < 7; r++) {
      var cd = addDays(start, w * 7 + r);
      var cell = document.createElement("div");
      cell.className = "u-cell";
      if (cd > end) {
        cell.style.visibility = "hidden";
      } else {
        var k = iso(cd);
        var day = data.days[k];
        var t = day ? dayOut(day) : 0;
        if (t > 0) {
          var dom = "terminal", best = -1;
          SURF.forEach(function (c) {
            var v = day[c[0]] ? day[c[0]].out : 0;
            if (v > best) { best = v; dom = c[0]; }
          });
          var lvl = Math.max(1, Math.min(4, Math.ceil(t / max * 4)));
          cell.className = "u-cell u-" + dom + "-" + lvl;
          cell.tabIndex = 0;
          cell.setAttribute("role", "button");
          cell.setAttribute("aria-label", k + ": " + fmt(t) + " output tokens");
          cell.addEventListener("click", function (k, day) {
            return function () { openModal(k, day); };
          }(k, day));
          cell.addEventListener("keydown", function (k, day) {
            return function (e) { if (e.key === "Enter" || e.key === " ") openModal(k, day); };
          }(k, day));
          cell.addEventListener("mouseenter", function (cell, k, day, t) {
            return function () { showTip(cell, k, day, t); };
          }(cell, k, day, t));
          cell.addEventListener("focus", function (cell, k, day, t) {
            return function () { showTip(cell, k, day, t); };
          }(cell, k, day, t));
          cell.addEventListener("mouseleave", hideTip);
          cell.addEventListener("blur", hideTip);
        }
      }
      col.appendChild(cell);
    }
    grid.appendChild(col);
  }

  var chart = document.getElementById("u-chart");
  var labels = document.getElementById("u-blabels");
  var weeks = [];
  var wmax = 0;
  for (var w2 = 41; w2 < 53; w2++) {
    var agg = { terminal: 0, desktop: 0 };
    for (var r2 = 0; r2 < 7; r2++) {
      var dk = iso(addDays(start, w2 * 7 + r2));
      var dd = data.days[dk];
      if (dd) SURF.forEach(function (c) { if (dd[c[0]]) agg[c[0]] += dd[c[0]].out; });
    }
    agg.start = addDays(start, w2 * 7);
    agg.total = agg.terminal + agg.desktop;
    if (agg.total > wmax) wmax = agg.total;
    weeks.push(agg);
  }
  weeks.forEach(function (wk) {
    var bar = document.createElement("div");
    bar.className = "u-bar";
    bar.title = "week of " + iso(wk.start) + " \\u2014 terminal " + fmt(wk.terminal) +
      " \\u00b7 desktop " + fmt(wk.desktop);
    SURF.forEach(function (c) {
      if (!wk[c[0]]) return;
      var seg = document.createElement("div");
      seg.className = "u-seg u-" + c[0] + "-3";
      seg.style.height = Math.max(1, Math.round(wk[c[0]] / (wmax || 1) * 104)) + "px";
      bar.appendChild(seg);
    });
    chart.appendChild(bar);
    var bl = document.createElement("span");
    bl.textContent = (wk.start.getMonth() + 1) + "/" + wk.start.getDate();
    labels.appendChild(bl);
  });
})();
"""


def usage_fragment(usage: dict, chevron_icon: str) -> tuple[str, str, str]:
    """Render the Claude usage section for the asicdash HTML report.

    Args:
        usage: Payload from collect_usage().
        chevron_icon: Inline SVG used by the report's <summary> rows, so the
            section header matches the other collapsible sections.

    Returns:
        (css, html, js) strings, inserted by html_report.render_html().
    """
    t = usage["totals"]
    meta = (
        f"{t['active_days']} active days · {t['sessions']} sessions"
        f" · ~{_fmt_tokens(t['out'])} output tokens"
    )
    # Token totals at four granularities — the at-a-glance answer to "how much have I used".
    p = t["periods"]
    tot = (
        '<div class="u-tot">'
        + "".join(
            f'<div class="u-tot-c"><div class="u-tot-l">{lbl}</div>'
            f'<div class="u-tot-v">{_fmt_tokens(p[k]["out"])} <span class="u-tot-u">out</span></div>'
            f'<div class="u-tot-s">{_fmt_tokens(p[k]["inp"])} in</div></div>'
            for lbl, k in (
                ("Today", "today"),
                ("Last 7 days", "d7"),
                ("Last 30 days", "d30"),
                ("All-time", "all"),
            )
        )
        + "</div>"
    )
    legend = (
        '<div class="u-legend">'
        '<span><span class="u-sw u-terminal-3"></span>Terminal</span>'
        '<span><span class="u-sw u-desktop-3"></span>Desktop app</span>'
        '<span class="na"><span class="u-sw u-chat-3"></span>Chat — no local data</span>'
        "</div>"
    )
    dows = (
        '<div class="u-dows"><span></span><span>Mon</span><span></span>'
        "<span>Wed</span><span></span><span>Fri</span><span></span></div>"
    )
    scale = '<span class="u-cell"></span>' + "".join(
        f'<span class="u-cell u-terminal-{i}"></span>' for i in range(1, 5)
    )
    html_out = (
        f'<details class="sec" open><summary>{chevron_icon}Claude usage'
        f'<span class="meta">{meta}</span></summary>'
        f'<div class="u-wrap">{tot}{legend}'
        '<div class="u-months" id="u-months"></div>'
        f'<div class="u-hm">{dows}<div class="u-grid" id="u-grid"></div></div>'
        '<div class="u-tip" id="u-tip"></div>'
        '<div class="u-foot"><span>cell color = dominant surface · hover for breakdown'
        " · click for detail"
        f'</span><span class="u-scale">less {scale} more</span></div>'
        '<div class="u-chart-title">Output tokens per week, last 12 weeks</div>'
        '<div class="u-chart" id="u-chart"></div>'
        '<div class="u-blabels" id="u-blabels"></div>'
        "</div></details>"
        '<div class="u-overlay" id="u-overlay" role="dialog" aria-modal="true">'
        '<div class="u-modal"><div class="u-m-head"><span id="u-m-date"></span>'
        '<button id="u-m-close" type="button" aria-label="Close">Close</button></div>'
        '<p class="u-m-sub" id="u-m-sub"></p><div id="u-m-rows"></div></div></div>'
        f'<script type="application/json" id="u-data">{json.dumps(usage)}</script>'
    )
    return USAGE_CSS, html_out, USAGE_JS
