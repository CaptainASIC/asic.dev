#!/usr/bin/env python3
"""asicdash: config + usage dashboard for Claude Code.

Scans global (~/.claude) and project scope for skills, agents, commands,
rules, hooks, plugins, memory files, and MCP servers. Reports what
loads into every session (with token estimates), what is broken (missing
executables, bad frontmatter), what is shadowed by a narrower scope, and what is
not file-visible at all (cloud routines) -- labeled honestly instead
of silently skipped. The HTML report adds a Claude usage section built from
local session transcripts (see usage.py).

Stdlib only. Output: themed HTML report (default), --cli table, or --json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import webbrowser
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from scanners import (
    CHARS_PER_TOKEN,
    Entry,
    scan_agents_md,
    scan_hook_scripts,
    scan_mcp,
    scan_md_dir,
    scan_memory_files,
    scan_plugins,
    scan_settings,
    scan_skills,
    short,
)

HOME = Path.home()


def known_paths(project: Path) -> dict[str, Path]:
    """Every filesystem location asicdash knows about, in one place.

    Claude Code's config layout shifts between versions; fix breakage here,
    not inside scanners.
    """
    g = HOME / ".claude"
    proj_slug = re.sub(r"[/.]", "-", str(project))
    return {
        "claude_global_skills": g / "skills",
        "claude_global_agents": g / "agents",
        "claude_global_commands": g / "commands",
        "claude_global_rules": g / "rules",
        "claude_global_hook_scripts": g / "hooks",
        "claude_global_settings": g / "settings.json",
        "claude_global_settings_local": g / "settings.local.json",
        "claude_global_memory": g / "CLAUDE.md",
        "claude_managed_memory": g / "projects" / proj_slug / "memory" / "MEMORY.md",
        "claude_installed_plugins": g / "plugins" / "installed_plugins.json",
        "claude_user_state": HOME / ".claude.json",
        "claude_proj_skills": project / ".claude" / "skills",
        "claude_proj_agents": project / ".claude" / "agents",
        "claude_proj_commands": project / ".claude" / "commands",
        "claude_proj_rules": project / ".claude" / "rules",
        "claude_proj_settings": project / ".claude" / "settings.json",
        "claude_proj_settings_local": project / ".claude" / "settings.local.json",
        "claude_proj_memory": project / "CLAUDE.md",
        "claude_proj_memory_local": project / "CLAUDE.local.md",
        "claude_proj_mcp": project / ".mcp.json",
        "agents_md": project / "AGENTS.md",
    }


def routine_placeholder() -> Entry:
    return Entry(
        tool="claude",
        kind="routine",
        name="scheduled routines / cloud agents",
        scope="global",
        source="—",
        status="n/a: stored cloud-side; list with /schedule in Claude Code",
    )


def mark_shadowed(entries: list[Entry]) -> None:
    """Project-scope skill/agent/command with the same name wins over global."""
    project_keys = {
        (e.tool, e.kind, e.name) for e in entries if e.scope == "project" and e.status == "ok"
    }
    for e in entries:
        if (
            e.scope == "global"
            and e.kind in ("skill", "agent", "command")
            and (e.tool, e.kind, e.name) in project_keys
        ):
            e.status = "shadowed by project"


def collect(project: Path) -> list[Entry]:
    paths = known_paths(project)
    registered: list[str] = []
    entries: list[Entry] = []
    entries += scan_skills(paths["claude_global_skills"], "global")
    entries += scan_md_dir(paths["claude_global_agents"], "agent", "global")
    entries += scan_md_dir(paths["claude_global_commands"], "command", "global")
    entries += scan_md_dir(paths["claude_global_rules"], "rule", "global", autoloaded=True)
    entries += scan_settings(paths["claude_global_settings"], "global", project, registered)
    entries += scan_settings(paths["claude_global_settings_local"], "global", project, registered)
    entries += scan_skills(paths["claude_proj_skills"], "project")
    entries += scan_md_dir(paths["claude_proj_agents"], "agent", "project")
    entries += scan_md_dir(paths["claude_proj_commands"], "command", "project")
    entries += scan_md_dir(paths["claude_proj_rules"], "rule", "project", autoloaded=True)
    entries += scan_settings(paths["claude_proj_settings"], "project", project, registered)
    entries += scan_settings(paths["claude_proj_settings_local"], "local", project, registered)
    entries += scan_memory_files(paths)
    entries += scan_plugins(paths, project, registered)
    entries += scan_hook_scripts(paths["claude_global_hook_scripts"], registered)
    entries += scan_mcp(paths, project)
    entries.append(routine_placeholder())
    entries += scan_agents_md(paths)
    mark_shadowed(entries)
    return entries


# ---------------------------------------------------------------------------
# rendering


def section_of(e: Entry) -> str:
    if e.kind == "plugin" or e.scope.startswith("plugin:"):
        return "CLAUDE CODE — PLUGINS"
    if e.scope == "global":
        return "CLAUDE CODE — GLOBAL"
    return "CLAUDE CODE — PROJECT"


SECTIONS = ["CLAUDE CODE — GLOBAL", "CLAUDE CODE — PROJECT", "CLAUDE CODE — PLUGINS"]


def paint(text: str, code: str, enabled: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if enabled else text


def status_color(status: str) -> str:
    if status.startswith("broken"):
        return "31"  # red
    if status.startswith(("shadowed", "unregistered")):
        return "33"  # yellow
    if status.startswith("n/a"):
        return "2"  # dim
    return "32"  # green


def clip(text: str, width: int) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def render(entries: list[Entry], project: Path, color: bool) -> None:
    term_width = shutil.get_terminal_size(fallback=(120, 40)).columns
    w_kind, w_name, w_status, w_tok = 12, 36, 28, 6
    w_detail = max(20, term_width - (w_kind + w_name + w_status + w_tok + 8))

    print(paint(f"asicdash — {short(project)}", "1", color))
    for section in SECTIONS:
        rows = [e for e in entries if section_of(e) == section]
        if not rows:
            continue
        print()
        print(paint(section, "1", color))
        print(paint("-" * min(term_width, 100), "2", color))
        for e in sorted(rows, key=lambda x: (x.kind, x.scope, x.name.lower())):
            tok = f"{e.tokens:>5}" if e.tokens else "     "
            detail = e.desc if e.desc else e.source
            line = "  ".join(
                [
                    clip(e.kind, w_kind).ljust(w_kind),
                    clip(
                        f"{e.name} [{e.scope}]" if section.endswith("PLUGINS") else e.name, w_name
                    ).ljust(w_name),
                    paint(clip(e.status, w_status).ljust(w_status), status_color(e.status), color),
                    tok,
                    paint(clip(detail, w_detail), "2", color),
                ]
            )
            print("  " + line)
    print()
    summarize(entries, project, color)


def attention_of(entries: list[Entry]) -> list[tuple[Entry, str]]:
    """Items worth flagging: busy hooks (even when nominally ok) plus outright problems."""
    flagged: list[tuple[Entry, str]] = []
    # hooks firing on many events run a process constantly; surface even when "ok"
    for e in entries:
        if e.kind != "hook":
            continue
        m = re.match(r"(\d+) event", e.desc)
        if m and int(m.group(1)) >= 10:
            flagged.append((e, f"fires on {m.group(1)} events; spawns a process each time"))
    flagged += [
        (e, e.status)
        for e in entries
        if e.status.startswith(("broken", "shadowed", "unregistered"))
    ]
    return flagged


def build_report(entries: list[Entry], project: Path) -> dict:
    """Everything a renderer needs as plain data — shared by --json, --html, and SUMMARY."""
    att = attention_of(entries)
    reasons = {id(e): reason for e, reason in att}
    counts = Counter(e.kind for e in entries if not e.status.startswith("n/a"))
    return {
        "project": str(project),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "summary": {
            "counts": dict(sorted(counts.items())),
            "always_loaded_tokens": sum(e.tokens for e in entries),
            "desc_tokens": sum(
                len(e.desc) // CHARS_PER_TOKEN
                for e in entries
                if e.kind in ("skill", "agent", "command") and e.status == "ok"
            ),
            "problems": sum(
                e.status.startswith(("broken", "shadowed", "unregistered")) for e in entries
            ),
            "attention": [
                {"kind": e.kind, "name": e.name, "detail": reason, "source": e.source}
                for e, reason in att
            ],
        },
        "entries": [
            asdict(e) | {"section": section_of(e), "attention": reasons.get(id(e), "")}
            for e in entries
        ],
    }


def summarize(entries: list[Entry], project: Path, color: bool) -> None:
    s = build_report(entries, project)["summary"]
    print(paint("SUMMARY", "1", color))
    print(paint("-" * 100, "2", color))
    print("  " + ", ".join(f"{k}: {v}" for k, v in s["counts"].items()))
    print(f"  always-loaded context: ~{s['always_loaded_tokens']} tokens (memory/rules files)")
    print(
        f"  plus ~{s['desc_tokens']} tokens of skill/agent/command descriptions"
        " in the system prompt"
    )
    if s["attention"]:
        print(paint(f"  attention ({len(s['attention'])}):", "33", color))
        for a in s["attention"]:
            print(f"    {a['kind']} {a['name']!r} — {a['detail']} ({a['source']})")
    else:
        print(paint("  no broken, shadowed, or unregistered items", "32", color))
    print(paint("  tip: run without --cli for the themed HTML report with usage stats", "2", color))


def to_json(entries: list[Entry], project: Path) -> str:
    return json.dumps(build_report(entries, project), indent=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="asicdash",
        description="Config + usage dashboard for Claude Code."
        " Default: themed HTML report opened in the browser.",
    )
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="aligned table on stdout (chat-friendly)")
    mode.add_argument("--json", action="store_true", help="machine-readable output")
    mode.add_argument(
        "--html",
        nargs="?",
        const="",
        metavar="PATH",
        help="HTML report path (default mode; PATH defaults to the system temp dir)",
    )
    ap.add_argument("--no-open", action="store_true", help="HTML mode: do not open a browser")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colors (--cli)")
    args = ap.parse_args(argv)

    project = args.project.expanduser().resolve()
    entries = collect(project)
    if args.json:
        print(to_json(entries, project))
        return 0
    if args.cli:
        color = sys.stdout.isatty() and not args.no_color
        render(entries, project, color)
        return 0
    # sibling modules; imported lazily so --cli/--json never depend on them
    from html_report import render_html
    from usage import collect_usage

    report = build_report(entries, project)
    report["usage"] = collect_usage()
    out = (
        Path(tempfile.gettempdir()) / f"asicdash-{project.name}.html"
        if args.html in (None, "")
        else Path(args.html).expanduser()
    )
    out.write_text(render_html(report), encoding="utf-8")
    print(f"report written: {short(out)}")
    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
