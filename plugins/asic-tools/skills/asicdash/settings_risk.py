"""asicdash settings risk: allow rules that run arbitrary code, env vars that override routing.

Split from scanners.py (PRP-027) so scanners stays under the 500-line cap. Imports helpers from
scanners; scanners never imports this module (the PRP-018 one-way rule). Names only, never env
values. Stdlib only.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from scanners import Entry, load_json, short

# Allow rules auto mode drops because they grant arbitrary code execution
# (code.claude.com/docs/en/permission-modes). In Manual/acceptEdits mode they still apply.
WHOLE_TOOL_RULES = frozenset(
    {"Bash", "Bash(*)", "PowerShell", "PowerShell(*)", "Agent", "Agent(*)", "Monitor", "Monitor(*)"}
)
INTERPRETERS = frozenset(
    {
        "python",
        "python3",
        "node",
        "deno",
        "bun",
        "ruby",
        "perl",
        "php",
        "bash",
        "sh",
        "zsh",
        "osascript",
    }
)
PACKAGE_RUNNERS = frozenset({"npm run", "npx", "pnpm", "yarn", "bunx", "uv run", "uvx"})
ROUTING_OVERRIDES = {
    "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": (
        "every subagent runs one model; agent `model:` and workflow ROUTING blocks are ignored"
    ),
    "CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL": (
        "every workflow agent runs one model; workflow ROUTING blocks are ignored"
    ),
}


def broad_allows(rules: list[str]) -> list[str]:
    """Allow rules broad enough to run arbitrary code without a prompt.

    A wildcard rule counts only when nothing specific precedes the `*`: `Bash(python3 *)` is
    broad, `Bash(uv run pytest *)` is not. The legacy `Bash(python3:*)` form is handled.

    Args:
        rules: A settings file's permissions.allow list.

    Returns:
        The subset of rules, in input order, that grant arbitrary code execution.
    """
    hits: list[str] = []
    for rule in rules:
        r = str(rule).strip()
        if r in WHOLE_TOOL_RULES:
            hits.append(rule)
        elif r.startswith("Bash(") and r.endswith(")") and "*" in r:
            head = r[len("Bash(") : -1].split("*", 1)[0].strip().rstrip(":").strip()
            if head in INTERPRETERS or head in PACKAGE_RUNNERS:
                hits.append(rule)
    return hits


def routing_env_entries(names: Mapping[str, object], scope: str, source: str) -> list[Entry]:
    """One `env` entry per routing-override var present in `names`. Names only, never values."""
    return [
        Entry("claude", "env", f"routing override: {n}", scope, source, desc=ROUTING_OVERRIDES[n])
        for n in sorted(ROUTING_OVERRIDES)
        if n in names
    ]


def scan_process_env() -> list[Entry]:
    """Routing-relevant vars in this process's environment.

    When Claude Code runs the skill, settings `env` blocks are already in os.environ, so this also
    catches vars set through settings. CLAUDE_CODE_SUBAGENT_MODEL alone is informational: it only
    reaches agents that declare no model, which attention_of() already flags.
    """
    entries = routing_env_entries(os.environ, "global", "process environment")
    if os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL"):
        entries.append(
            Entry(
                "claude",
                "env",
                "CLAUDE_CODE_SUBAGENT_MODEL",
                "global",
                "process environment",
                desc="default model for subagents that declare none (env step of resolution)",
            )
        )
    return entries


# The four settings files asicdash.collect() passes to scan_settings(), with the same scopes.
SETTINGS_FILES = (
    ("claude_global_settings", "global"),
    ("claude_global_settings_local", "global"),
    ("claude_proj_settings", "project"),
    ("claude_proj_settings_local", "local"),
)


def scan_settings_risk(paths: dict[str, Path]) -> list[Entry]:
    """Broad allow rules and routing-override env names, per settings file and scope.

    An absent or invalid file yields nothing here; scan_settings() already reports invalid JSON.

    Args:
        paths: asicdash.known_paths() output.

    Returns:
        One `permissions` entry (desc starts "broad allow: ") per file with broad rules, plus one
        `routing override: <VAR>` env entry per override var named in the file's env block.
    """
    entries: list[Entry] = []
    for key, scope in SETTINGS_FILES:
        path = paths[key]
        data = load_json(path) if path.is_file() else {}
        if not isinstance(data, dict):
            continue
        broad = broad_allows((data.get("permissions") or {}).get("allow") or [])
        if broad:
            entries.append(
                Entry(
                    tool="claude",
                    kind="permissions",
                    name=f"{len(broad)} broad allow rule(s)",
                    scope=scope,
                    source=short(path),
                    desc="broad allow: " + ", ".join(broad),  # anchor: attention_of startswith
                )
            )
        entries += routing_env_entries(data.get("env") or {}, scope, short(path))
    return entries
