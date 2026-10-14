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
