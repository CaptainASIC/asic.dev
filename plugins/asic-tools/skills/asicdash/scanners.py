"""asicdash scanners: every filesystem probe, and the shapes they return.

Split out of asicdash.py (PRP-018) once that module passed the 500-line cap. Holds `Entry`,
the small helpers, and the non-plugin `scan_*` functions (plugin scanning lives in
plugins_scan.py, PRP-027).

**Dependency direction is one-way: this module never imports asicdash.py.** Every helper a
scanner touches lives here, including the ones asicdash.py also uses -- it imports them back.
Leaving one behind creates asicdash -> scanners -> asicdash, which raises
`ImportError: cannot import name 'scan_...' from partially initialized module`.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

HOME = Path.home()
CHARS_PER_TOKEN = 4  # crude but stable estimate for always-loaded cost
TOKEN_RUN = re.compile(r"[A-Za-z0-9_-]{24,}")


@dataclass
class Entry:
    """One discovered config item."""

    tool: str  # claude
    # kind: skill | agent | command | rule | hook | hook-script | plugin | memory | mcp | workflow |
    # permissions | env | routine | mod | lsp | output-style | theme | monitor | bin | plugin-settings
    kind: str
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


def redact_url(value: str) -> str:
    """Strip userinfo, query and fragment from a URL so a key inside it never reaches a report.

    Args:
        value: An MCP config's command, url, or transport type.

    Returns:
        `scheme://host[:port]/path`, with any 24+ character token run in the path masked as
        `[…]`, suffixed " (redacted)" when anything was dropped or masked. Values that are not
        URLs pass through unchanged.

    Example:
        >>> redact_url("https://api.example.com/mcp?apiKey=abc")
        'https://api.example.com/mcp (redacted)'
    """
    if "://" not in value:
        return value
    try:
        parts = urlsplit(value)
        port = parts.port  # Reason: .port raises ValueError on an out-of-range port.
    except ValueError:
        return "<unparseable url>"
    host = (parts.hostname or "") + (f":{port}" if port else "")
    # Reason: hosted MCP URLs often carry the key in the path (`/s/<token>/mcp`). Mask any run
    # of 24+ token characters, the same rule as prompt previews (§3.10).
    path = TOKEN_RUN.sub("[…]", parts.path)
    dropped = parts.query or parts.fragment or parts.username or parts.password
    clean = urlunsplit((parts.scheme, host, path, "", ""))
    return clean + (" (redacted)" if dropped or path != parts.path else "")


def mcp_desc(cfg: object) -> str:
    """Display text for one MCP server config: command, else url, else type. Always redacted."""
    if not isinstance(cfg, dict):
        return ""
    return redact_url(str(cfg.get("command") or cfg.get("url") or cfg.get("type") or ""))


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
        desc = fm.get("description", "")
        if kind == "agent":
            # Reason: model/effort are PREPENDED, not appended. Two reasons, both load-bearing:
            # clip() would cut an appended value off a 200+ char agent description in the CLI
            # table, and `model: ` at position 0 is an anchor no free-text prose can occupy --
            # which is what attention_of()'s unset-model flag tests with startswith().
            bits = [f"model: {fm[k]}" for k in ("model",) if fm.get(k)]
            bits += [f"effort: {fm[k]}" for k in ("effort",) if fm.get(k)]
            if bits:
                joined = " · ".join(bits)
                desc = f"{joined} — {desc}" if desc else joined
        # Reason: a rule with `paths:` loads only when Claude touches a matching file (memory
        # docs, path-specific rules), so it is not part of the always-loaded figure. The
        # frontmatter reader keeps the key even when its value is a block list (value "").
        conditional = kind == "rule" and "paths" in fm
        if conditional:
            desc = "conditional (paths) — loads when matching files are touched" + (
                f"; {desc}" if desc else ""
            )
        entries.append(
            Entry(
                tool="claude",
                kind=kind,
                name=fm.get("name", rel),
                scope=scope,
                source=short(f),
                desc=desc,
                # agents require frontmatter; commands and rules may be plain markdown
                status=f"broken: {err}" if err and kind == "agent" else "ok",
                tokens=est_tokens(f) if autoloaded and not conditional else 0,
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


def scan_agents_md(paths: dict[str, Path]) -> list[Entry]:
    """Project AGENTS.md — the cross-tool agent-rules convention, read by Claude Code."""
    entries: list[Entry] = []
    p = paths["agents_md"]
    if p.is_file():
        entries.append(
            Entry(
                "claude",
                "rule",
                p.name,
                "project",
                short(p),
                desc="agent rules file (AGENTS.md convention)",
                tokens=est_tokens(p),
            )
        )
    return entries
