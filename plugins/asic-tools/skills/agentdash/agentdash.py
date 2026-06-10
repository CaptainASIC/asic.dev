#!/usr/bin/env python3
"""agentdash: audit visible and invisible agent-harness config for Claude Code and Warp.

Scans global (~/.claude, ~/.warp) and project scope for skills, agents, commands,
rules, hooks, plugins, memory files, MCP servers, and Warp workflows. Reports what
loads into every session (with token estimates), what is broken (missing
executables, bad frontmatter), what is shadowed by a narrower scope, and what is
not file-visible at all (Warp Drive, cloud routines) -- labeled honestly instead
of silently skipped.

Stdlib only. Output: aligned table (default) or --json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

HOME = Path.home()
CHARS_PER_TOKEN = 4  # crude but stable estimate for always-loaded cost


def known_paths(project: Path) -> dict[str, Path]:
    """Every filesystem location agentdash knows about, in one place.

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
        "warp_global_workflows": HOME / ".warp" / "workflows",
        "warp_proj_workflows": project / ".warp" / "workflows",
        "warp_proj_rules": project / "WARP.md",
        "agents_md": project / "AGENTS.md",
        "warp_app_support": HOME / "Library" / "Application Support" / "dev.warp.Warp-Stable",
    }


@dataclass
class Entry:
    """One discovered config item."""

    tool: str  # claude | warp
    kind: str  # skill | agent | command | rule | hook | hook-script | plugin | memory | mcp | workflow | permissions | env | routine
    name: str
    scope: str  # global | project | local | plugin:<name>
    source: str  # origin path, ~-shortened
    desc: str = ""
    status: str = "ok"  # ok | shadowed by project | unregistered | broken: ... | n/a: ...
    tokens: int = 0  # estimated tokens if loaded into every session, else 0


# ---------------------------------------------------------------------------
# small helpers


def short(path: Path | str) -> str:
    s = str(path)
    home = str(HOME)
    return "~" + s[len(home) :] if s.startswith(home) else s


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def est_tokens(path: Path) -> int:
    try:
        return max(1, path.stat().st_size // CHARS_PER_TOKEN)
    except OSError:
        return 0


def load_json(path: Path) -> dict:
    try:
        data = json.loads(read_text(path) or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str | None]:
    """Tolerant YAML frontmatter reader.

    Handles top-level `key: value` pairs plus folded/literal blocks (`key: >`)
    well enough to extract name and description. Returns (fields, error).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "no frontmatter"
    fields: dict[str, str] = {}
    block_key: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in ("---", "..."):
            return fields, None
        if block_key is not None:
            if line[:1] in (" ", "\t") or not stripped:
                fields[block_key] = (fields[block_key] + " " + stripped).strip()
                continue
            block_key = None
        if not line or line[0] in " \t" or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip().strip("\"'")
        if value in (">", "|", ">-", "|-", ">+", "|+"):
            fields[key] = ""
            block_key = key
        else:
            fields[key] = value
    return fields, "unterminated frontmatter"


def parse_yaml_top(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs from a YAML doc (Warp workflow files)."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line[0] in " \t#-" or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip().strip("\"'")
    return fields


def command_status(command: str, project: Path, plugin_root: Path | None = None) -> str:
    """Check that a hook command's executable actually exists on this machine."""
    cmd = command.replace("${CLAUDE_PROJECT_DIR}", str(project))
    cmd = cmd.replace("$CLAUDE_PROJECT_DIR", str(project))
    if plugin_root is not None:
        cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
        cmd = cmd.replace("$CLAUDE_PLUGIN_ROOT", str(plugin_root))
    try:
        head = shlex.split(cmd)[0]
    except (ValueError, IndexError):
        return "broken: unparseable command"
    head = os.path.expanduser(head)
    if "/" in head:
        return "ok" if Path(head).exists() else f"broken: missing {short(head)}"
    return "ok" if shutil.which(head) else f"broken: {head!r} not on PATH"


def command_label(command: str) -> str:
    """Compact display name for a hook command: basenames of binary and path args."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return command[:48]
    if not parts:
        return command[:48]
    return " ".join(Path(p).name if "/" in p else p for p in parts[:3])


def flatten_hooks(hooks_obj: dict) -> dict[str, list[str]]:
    """Flatten Claude's hooks structure into {command: [event[matcher], ...]}."""
    by_command: dict[str, list[str]] = {}
    for event, matchers in hooks_obj.items():
        if not isinstance(matchers, list):
            continue
        for m in matchers:
            if not isinstance(m, dict):
                continue
            label = event + (f"[{m.get('matcher')}]" if m.get("matcher") else "")
            for h in m.get("hooks", []):
                cmd = (h.get("command") or "").strip() if isinstance(h, dict) else ""
                if cmd:
                    by_command.setdefault(cmd, []).append(label)
    return by_command


# ---------------------------------------------------------------------------
# scanners


def scan_skills(root: Path, scope: str) -> list[Entry]:
    entries: list[Entry] = []
    if not root.is_dir():
        return entries
    for sub in sorted(root.iterdir()):
        manifest = sub / "SKILL.md"
        if not sub.is_dir() or not manifest.is_file():
            continue
        fm, err = parse_frontmatter(read_text(manifest))
        entries.append(
            Entry(
                tool="claude",
                kind="skill",
                name=fm.get("name", sub.name),
                scope=scope,
                source=short(manifest),
                desc=fm.get("description", ""),
                status=f"broken: {err}" if err else "ok",
            )
        )
    return entries


def scan_md_dir(root: Path, kind: str, scope: str, autoloaded: bool = False) -> list[Entry]:
    entries: list[Entry] = []
    if not root.is_dir():
        return entries
    for f in sorted(root.rglob("*.md")):
        fm, err = parse_frontmatter(read_text(f))
        rel = str(f.relative_to(root).with_suffix(""))
        entries.append(
            Entry(
                tool="claude",
                kind=kind,
                name=fm.get("name", rel),
                scope=scope,
                source=short(f),
                desc=fm.get("description", ""),
                # agents require frontmatter; commands and rules may be plain markdown
                status=f"broken: {err}" if err and kind == "agent" else "ok",
                tokens=est_tokens(f) if autoloaded else 0,
            )
        )
    return entries


def scan_memory_files(paths: dict[str, Path]) -> list[Entry]:
    candidates = [
        ("global", paths["claude_global_memory"]),
        ("global", paths["claude_managed_memory"]),
        ("project", paths["claude_proj_memory"]),
        ("local", paths["claude_proj_memory_local"]),
    ]
    return [
        Entry(
            tool="claude",
            kind="memory",
            name=p.name if p.name != "MEMORY.md" else "MEMORY.md (managed memory index)",
            scope=scope,
            source=short(p),
            desc="auto-loaded into every session in this project",
            tokens=est_tokens(p),
        )
        for scope, p in candidates
        if p.is_file()
    ]


def scan_settings(path: Path, scope: str, project: Path, registered: list[str]) -> list[Entry]:
    entries: list[Entry] = []
    if not path.is_file():
        return entries
    data = load_json(path)
    if not data:
        entries.append(
            Entry("claude", "hook", path.name, scope, short(path), status="broken: invalid JSON")
        )
        return entries
    for cmd, events in sorted(flatten_hooks(data.get("hooks") or {}).items()):
        registered.append(cmd)
        entries.append(
            Entry(
                tool="claude",
                kind="hook",
                name=command_label(cmd),
                scope=scope,
                source=short(path),
                desc=f"{len(events)} event(s): " + ", ".join(events),
                status=command_status(cmd, project),
            )
        )
    status_line = data.get("statusLine")
    if isinstance(status_line, dict) and status_line.get("command"):
        cmd = status_line["command"]
        registered.append(cmd)
        entries.append(
            Entry(
                tool="claude",
                kind="hook",
                name="statusLine: " + command_label(cmd),
                scope=scope,
                source=short(path),
                desc="renders the status line every prompt",
                status=command_status(cmd, project),
            )
        )
    perms = data.get("permissions") or {}
    n_allow, n_ask, n_deny = (len(perms.get(k) or []) for k in ("allow", "ask", "deny"))
    if n_allow or n_ask or n_deny:
        preview = ", ".join((perms.get("allow") or [])[:4])
        entries.append(
            Entry(
                tool="claude",
                kind="permissions",
                name=f"{n_allow} allow / {n_ask} ask / {n_deny} deny",
                scope=scope,
                source=short(path),
                desc=preview,
            )
        )
    env = data.get("env") or {}
    if env:
        entries.append(
            Entry(
                tool="claude",
                kind="env",
                name=f"{len(env)} var(s)",
                scope=scope,
                source=short(path),
                desc=", ".join(sorted(env)[:6]),
            )
        )
    return entries


def scan_plugins(paths: dict[str, Path], project: Path, registered: list[str]) -> list[Entry]:
    entries: list[Entry] = []
    data = load_json(paths["claude_installed_plugins"])
    for full_name, installs in sorted((data.get("plugins") or {}).items()):
        name = full_name.split("@")[0]
        scope = f"plugin:{name}"
        install = installs[0] if isinstance(installs, list) and installs else {}
        root = Path(install.get("installPath", "/nonexistent"))
        meta = load_json(root / ".claude-plugin" / "plugin.json")
        entries.append(
            Entry(
                tool="claude",
                kind="plugin",
                name=full_name,
                scope=install.get("scope", "user"),
                source=short(root),
                desc=meta.get("description", ""),
                status="ok" if root.is_dir() else "broken: install path missing",
            )
        )
        if not root.is_dir():
            continue
        entries += scan_skills(root / "skills", scope)
        for e in scan_md_dir(root / "agents", "agent", scope):
            entries.append(e)
        for e in scan_md_dir(root / "commands", "command", scope):
            entries.append(e)
        hooks_file = root / "hooks" / "hooks.json"
        for cmd, events in sorted(flatten_hooks(load_json(hooks_file).get("hooks") or {}).items()):
            registered.append(cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(root)))
            entries.append(
                Entry(
                    tool="claude",
                    kind="hook",
                    name=command_label(cmd),
                    scope=scope,
                    source=short(hooks_file),
                    desc=f"{len(events)} event(s): " + ", ".join(events),
                    status=command_status(cmd, project, plugin_root=root),
                )
            )
    return entries


def scan_hook_scripts(root: Path, registered: list[str]) -> list[Entry]:
    """Files in ~/.claude/hooks that nothing references: likely rot.

    References checked: hook registrations (settings + plugins) and sibling
    scripts in the same directory (a registered hook may require/source others).
    """
    entries: list[Entry] = []
    if not root.is_dir():
        return entries
    skip = {"package.json", "package-lock.json", "node_modules", ".DS_Store"}
    files = [f for f in sorted(root.iterdir()) if f.is_file() and f.name not in skip]
    for f in files:
        blob = "\n".join(registered) + "\n".join(
            read_text(sibling) for sibling in files if sibling != f
        )
        # stem too: node scripts get required extensionless (require('./caveman-config'))
        referenced = f.name in blob or f.stem in blob
        entries.append(
            Entry(
                tool="claude",
                kind="hook-script",
                name=f.name,
                scope="global",
                source=short(f),
                desc=""
                if referenced
                else "not referenced by hook registrations or sibling scripts; may be skill-invoked",
                status="ok" if referenced else "unregistered",
            )
        )
    return entries


def scan_mcp(paths: dict[str, Path], project: Path) -> list[Entry]:
    entries: list[Entry] = []

    def mcp_desc(cfg: object) -> str:
        if not isinstance(cfg, dict):
            return ""
        return str(cfg.get("command") or cfg.get("url") or cfg.get("type") or "")

    proj_mcp = load_json(paths["claude_proj_mcp"])
    for name, cfg in sorted((proj_mcp.get("mcpServers") or {}).items()):
        entries.append(
            Entry(
                "claude",
                "mcp",
                name,
                "project",
                short(paths["claude_proj_mcp"]),
                desc=mcp_desc(cfg),
            )
        )
    state = load_json(paths["claude_user_state"])
    for name, cfg in sorted((state.get("mcpServers") or {}).items()):
        entries.append(
            Entry(
                "claude",
                "mcp",
                name,
                "global",
                short(paths["claude_user_state"]),
                desc=mcp_desc(cfg),
            )
        )
    proj_state = (state.get("projects") or {}).get(str(project)) or {}
    for name, cfg in sorted((proj_state.get("mcpServers") or {}).items()):
        entries.append(
            Entry(
                "claude",
                "mcp",
                name,
                "project",
                short(paths["claude_user_state"]),
                desc=mcp_desc(cfg),
            )
        )
    return entries


def scan_warp(paths: dict[str, Path]) -> list[Entry]:
    entries: list[Entry] = []
    for scope, root in (
        ("global", paths["warp_global_workflows"]),
        ("project", paths["warp_proj_workflows"]),
    ):
        if not root.is_dir():
            continue
        for f in sorted(root.iterdir()):
            if f.suffix not in (".yaml", ".yml"):
                continue
            fields = parse_yaml_top(read_text(f))
            entries.append(
                Entry(
                    tool="warp",
                    kind="workflow",
                    name=fields.get("name", f.stem),
                    scope=scope,
                    source=short(f),
                    desc=fields.get("description", ""),
                )
            )
    for p, note in (
        (paths["warp_proj_rules"], "Warp project rules, auto-loaded into agent context"),
        (paths["agents_md"], "agent rules file (read by Warp and other tools)"),
    ):
        if p.is_file():
            entries.append(
                Entry("warp", "rule", p.name, "project", short(p), desc=note, tokens=est_tokens(p))
            )
    app = paths["warp_app_support"]
    entries.append(
        Entry(
            tool="warp",
            kind="rule",
            name="Warp Drive (rules, workflows, profiles)",
            scope="global",
            source=short(app) if app.is_dir() else "—",
            status="n/a: cloud-synced SQLite, not file-visible; check Warp Drive UI",
        )
    )
    mcp_dir = app / "mcp"
    if mcp_dir.is_dir():
        logs = [f.stem for f in sorted(mcp_dir.iterdir()) if f.is_file()]
        if logs:
            entries.append(
                Entry(
                    tool="warp",
                    kind="mcp",
                    name=f"mcp activity ({len(logs)} log file(s))",
                    scope="global",
                    source=short(mcp_dir),
                    desc="server config lives in Warp settings; logs: " + ", ".join(logs[:6]),
                )
            )
    return entries


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
    entries += scan_warp(paths)
    mark_shadowed(entries)
    return entries


# ---------------------------------------------------------------------------
# rendering


def section_of(e: Entry) -> str:
    if e.tool == "warp":
        return "WARP"
    if e.kind == "plugin" or e.scope.startswith("plugin:"):
        return "CLAUDE CODE — PLUGINS"
    if e.scope == "global":
        return "CLAUDE CODE — GLOBAL"
    return "CLAUDE CODE — PROJECT"


SECTIONS = ["CLAUDE CODE — GLOBAL", "CLAUDE CODE — PROJECT", "CLAUDE CODE — PLUGINS", "WARP"]


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

    print(paint(f"agentdash — {short(project)}", "1", color))
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
    summarize(entries, color)


def summarize(entries: list[Entry], color: bool) -> None:
    counts = Counter(e.kind for e in entries if not e.status.startswith("n/a"))
    always = sum(e.tokens for e in entries)
    desc_tokens = sum(
        len(e.desc) // CHARS_PER_TOKEN
        for e in entries
        if e.kind in ("skill", "agent", "command") and e.status == "ok"
    )
    problems = [e for e in entries if e.status.startswith(("broken", "shadowed", "unregistered"))]
    # hooks firing on many events run a process constantly; surface even when "ok"
    busy_hooks = []
    for e in entries:
        if e.kind != "hook":
            continue
        m = re.match(r"(\d+) event", e.desc)
        if m and int(m.group(1)) >= 10:
            busy_hooks.append((e, int(m.group(1))))
    print(paint("SUMMARY", "1", color))
    print(paint("-" * 100, "2", color))
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    print(f"  always-loaded context: ~{always} tokens (memory/rules files)")
    print(f"  plus ~{desc_tokens} tokens of skill/agent/command descriptions in the system prompt")
    if problems or busy_hooks:
        print(paint(f"  attention ({len(problems) + len(busy_hooks)}):", "33", color))
        for e, n in busy_hooks:
            print(
                f"    hook {e.name!r} fires on {n} events — spawns a process each time ({e.source})"
            )
        for e in problems:
            print(f"    {e.kind} {e.name!r} — {e.status} ({e.source})")
    else:
        print(paint("  no broken, shadowed, or unregistered items", "32", color))


def to_json(entries: list[Entry], project: Path) -> str:
    counts = Counter(e.kind for e in entries if not e.status.startswith("n/a"))
    payload = {
        "project": str(project),
        "summary": {
            "counts": dict(sorted(counts.items())),
            "always_loaded_tokens": sum(e.tokens for e in entries),
            "problems": sum(
                e.status.startswith(("broken", "shadowed", "unregistered")) for e in entries
            ),
        },
        "entries": [asdict(e) for e in entries],
    }
    return json.dumps(payload, indent=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="agentdash",
        description="Audit Claude Code + Warp agent config across global and project scope.",
    )
    ap.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: cwd)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = ap.parse_args(argv)

    project = args.project.expanduser().resolve()
    entries = collect(project)
    if args.json:
        print(to_json(entries, project))
        return 0
    color = sys.stdout.isatty() and not args.no_color
    render(entries, project, color)
    return 0


if __name__ == "__main__":
    sys.exit(main())
