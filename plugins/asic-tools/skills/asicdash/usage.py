"""Claude usage collector for the asicdash report (rendering lives in usage_html.py).

Aggregates per-day activity from local Claude Code session transcripts
(~/.claude/projects/**/*.jsonl). Every transcript here is a Claude Code
session; the entrypoint field only records how Code was launched, which is
the one split the local data can honestly make:

  terminal — launched from the CLI (entrypoint "cli")
  desktop  — launched from the Claude desktop app (entrypoint "claude-desktop")
  chat     — claude.ai web; leaves no local transcript, always shown as
             "no local data" rather than silently omitted

Counting (PRP-027; method adapted from claude-plugins-official session-report, Apache-2.0, no
code copied): Claude Code writes one assistant line per content block, sharing a requestId and
repeating usage, so each request counts once, keyed globally requestId -> message.id ->
path:uuid, keeping the line with the most output_tokens. Subagent and workflow-agent
transcripts (<project>/<session>/subagents/**/*.jsonl) roll into their parent session's day and
surface. Each call is attributed to the session's latest human prompt at or before it; a
nested file's calls all anchor at that file's first timestamp.
Stdlib only.
"""

from __future__ import annotations

import bisect
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

SURFACES = ("terminal", "desktop")  # surfaces with local data; chat is rendered as n/a
WINDOW_DAYS = 371  # 53 weeks, matching the heatmap span
TOP_PROMPTS = 10
PREVIEW_CHARS = 100
AUTO_PREFIXES = (
    "<task-notification",
    "<scheduled-wakeup",
    "<background-task",
    "[Request interrupted",
)
_TAG = re.compile(r"<[^>]+>")
_TOKENISH = re.compile(r"[A-Za-z0-9_\-]{24,}")  # Reason: masks pasted keys/tokens in previews.
_SLASH = re.compile(r"<command-(?:name|message)>/?([^<]+)</command-")


def surface_of(entrypoint: str) -> str:  # unchanged
    """Map a transcript entrypoint value onto a dashboard surface."""
    return "desktop" if "desktop" in entrypoint else "terminal"


@dataclass
class _Call:
    when: datetime
    anchor: datetime  # prompt-attribution time: nested file's first timestamp, else `when`
    session: str
    out: int
    inp: int
    c_read: int
    c_create: int


@dataclass
class _State:
    cutoff: datetime
    calls: dict[str, _Call] = field(default_factory=dict)
    entrypoint: dict[str, str] = field(default_factory=dict)
    prompts: dict[str, dict] = field(default_factory=dict)
    session_prompts: dict[str, list[tuple[datetime, str]]] = field(default_factory=dict)


def preview(text: str) -> str:
    """Report-safe prompt preview: slash command name, else tag-stripped, masked, truncated."""
    m = _SLASH.search(text)
    if m:
        return "/" + m.group(1).strip()
    flat = _TOKENISH.sub("[…]", " ".join(_TAG.sub(" ", text).split()))
    return flat if len(flat) <= PREVIEW_CHARS else flat[: PREVIEW_CHARS - 1] + "…"


def human_text(d: dict) -> str | None:
    """A main-transcript user line's prompt text, or None (tool results, meta, auto-continuations)."""
    if (
        d.get("type") != "user"
        or d.get("isSidechain")
        or d.get("isMeta")
        or d.get("isCompactSummary")
    ):
        return None
    content = (d.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif (
        isinstance(content, list)
        and content
        and isinstance(content[0], dict)
        and content[0].get("type") == "text"
    ):
        text = str(content[0].get("text") or "")
    else:
        return None
    return None if text.startswith(AUTO_PREFIXES) else text


def _when(ts: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts)).astimezone()
    except ValueError:
        return None


def _line_when(line: str) -> datetime | None:
    """The timestamp of one JSONL line, or None (unparseable line or no valid timestamp)."""
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return None
    return _when(d.get("timestamp", "")) if isinstance(d, dict) else None


def project_label(path: Path, root: Path) -> str:
    """'-Users-asic-Repositories-Airi' -> 'Repositories-Airi' (home prefix dropped)."""
    slug = path.relative_to(root).parts[0]
    home = re.sub(r"[/.]", "-", str(Path.home())) + "-"  # same slug rule as asicdash.py:53
    return slug.removeprefix(home)


def _scan(path: Path, root: Path, session: str, is_main: bool, st: _State) -> None:
    """Fold one transcript into the state: prompts (main files), entrypoint, deduped calls."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    # Reason: a nested file's calls are attributed at the file's FIRST timestamp (§3.9), not at
    # each call's own time; main-file calls use their own time (anchor None -> `when`).
    anchor = (
        None
        if is_main
        else next((w for w in (_line_when(ln) for ln in lines) if w is not None), None)
    )
    for line in lines:
        # Reason: nested transcripts only contribute calls; the substring pre-filter keeps the
        # 3,535-file nested scan at ~4 s (measured). Main files are parsed whole, as before.
        if not is_main and '"type":"assistant"' not in line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue
        if is_main and d.get("entrypoint") and session not in st.entrypoint:
            st.entrypoint[session] = str(d["entrypoint"])
        when = _when(d.get("timestamp", ""))
        if when is None:
            continue
        text = human_text(d) if is_main else None
        if text is not None:
            key = str(d.get("uuid") or f"{session}:{d.get('timestamp')}")
            st.prompts[key] = {
                "text": preview(text),
                "ts": when.isoformat(timespec="minutes"),
                "project": project_label(path, root),
                "session": session,
            }
            st.session_prompts.setdefault(session, []).append((when, key))
            continue
        msg = d.get("message")
        if d.get("type") != "assistant" or not isinstance(msg, dict) or when < st.cutoff:
            continue
        u = msg.get("usage") or {}
        call = _Call(
            when,
            anchor or when,
            session,
            int(u.get("output_tokens") or 0),
            int(u.get("input_tokens") or 0),
            int(u.get("cache_read_input_tokens") or 0),
            int(u.get("cache_creation_input_tokens") or 0),
        )
        key = str(d.get("requestId") or msg.get("id") or f"{path}:{d.get('uuid', '')}")
        prev = st.calls.get(key)
        if prev is None or call.out > prev.out:
            st.calls[key] = call


def hit_pct(agg: dict) -> int:
    """Cache hit as a whole percent: c_read / (inp + c_create + c_read); 0 when nothing was read."""
    denom = agg.get("inp", 0) + agg.get("c_create", 0) + agg.get("c_read", 0)
    return round(100 * agg.get("c_read", 0) / denom) if denom else 0


def _prompt_for(prompts: list[tuple[datetime, str]], when: datetime) -> str | None:
    i = bisect.bisect_right([t for t, _ in prompts], when) - 1
    return prompts[i][1] if i >= 0 else None


def collect_usage(root: Path | None = None, now: datetime | None = None) -> dict:
    """Aggregate per-day, per-surface Claude usage from local transcripts (main + nested).

    Args:
        root: Transcript root; defaults to ~/.claude/projects. Injected by tests.
        now: Clock; defaults to now. Injected by tests.

    Returns:
        "today", "days" (date -> surface -> out/inp/c_read/c_create/msgs/sessions) and "totals"
        (out, inp, c_read, c_create, active_days, sessions, periods, top_prompts), 53 weeks.
    """
    now = now or datetime.now().astimezone()
    root = root or Path.home() / ".claude" / "projects"
    st = _State(cutoff=now - timedelta(days=WINDOW_DAYS))
    if root.is_dir():
        for f in sorted(root.glob("*/*.jsonl")):  # main transcripts first: they set entrypoints
            _scan(f, root, f.stem, True, st)
        for f in sorted(root.glob("*/*/subagents/**/*.jsonl")):
            _scan(f, root, f.relative_to(root).parts[1], False, st)
    for plist in st.session_prompts.values():
        plist.sort(key=lambda p: p[0])
    return _aggregate(st, now)


def _aggregate(st: _State, now: datetime) -> dict:
    by_day: dict[str, dict] = {}
    per_prompt: dict[str, dict] = {}
    fields = ("out", "inp", "c_read", "c_create")
    for call in st.calls.values():
        surface = surface_of(st.entrypoint.get(call.session, ""))
        day = by_day.setdefault(call.when.date().isoformat(), {})
        agg = day.setdefault(surface, {**dict.fromkeys(fields, 0), "msgs": 0, "sids": set()})
        for f in fields:
            agg[f] += getattr(call, f)
        agg["msgs"] += 1
        agg["sids"].add(call.session)
        key = _prompt_for(st.session_prompts.get(call.session, []), call.anchor)  # not call.when
        if key:
            p = per_prompt.setdefault(key, dict.fromkeys(fields, 0))
            for f in fields:
                p[f] += getattr(call, f)
    days = {
        d: {
            s: {**{f: a[f] for f in fields}, "msgs": a["msgs"], "sessions": len(a["sids"])}
            for s, a in surfaces.items()
        }
        for d, surfaces in sorted(by_day.items())
    }
    today = now.date()
    bounds = {
        "today": today.isoformat(),
        "d7": (today - timedelta(days=6)).isoformat(),
        "d30": (today - timedelta(days=29)).isoformat(),
        "all": "",
    }
    periods = {
        k: {f: sum(a[f] for d, s in days.items() if d >= since for a in s.values()) for f in fields}
        for k, since in bounds.items()
    }
    top = sorted(per_prompt.items(), key=lambda kv: -sum(kv[1].values()))[:TOP_PROMPTS]
    sessions = {sid for s in by_day.values() for a in s.values() for sid in a["sids"]}
    return {
        "today": today.isoformat(),
        "days": days,
        "totals": {
            **{f: periods["all"][f] for f in fields},
            "active_days": len(days),
            "sessions": len(sessions),
            "periods": periods,
            "top_prompts": [
                {**st.prompts[k], "total": sum(v.values()), "out": v["out"], "hit": hit_pct(v)}
                for k, v in top
            ],
        },
    }
