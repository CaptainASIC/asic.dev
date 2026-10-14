"""asicdash plugin manifest helpers: effective manifest, contained paths, enabled state, roots.

Split out of plugins_scan (PRP-027) for the 500-line cap. Imports helpers from scanners only;
scanners never imports this module. Stdlib only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scanners import HOME, load_json, read_text

# Same files and order as settings_risk.SETTINGS_FILES; a later file overrides an earlier one.
# Reason: duplicated as path keys, not imported, because plugin_manifest must not import
# settings_risk (one-way import rule, §3.2).
ENABLED_SOURCES = (
    "claude_global_settings",
    "claude_global_settings_local",
    "claude_proj_settings",
    "claude_proj_settings_local",
)


def as_list(value: object) -> list:
    """A manifest value that may be one item or a list, as a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def contained(root: Path, items: object) -> list[Path]:
    """Manifest paths resolved under root; a path escaping the plugin root is dropped."""
    base = root.resolve()
    out: list[Path] = []
    for item in as_list(items):
        if isinstance(item, str):
            p = (root / item).resolve()
            if p == base or base in p.parents:
                out.append(p)
    return out


def load_array(path: Path) -> list:
    """A JSON file holding a top-level array (monitors.json); anything else reads as []."""
    try:
        data = json.loads(read_text(path) or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def marketplace_entry(full_name: str) -> dict:
    """This plugin's entry in its marketplace catalog, or {} when not found."""
    name, _, market = full_name.partition("@")
    registry = load_json(HOME / ".claude" / "plugins" / "known_marketplaces.json")
    location = (registry.get(market) or {}).get("installLocation")
    if not location:
        return {}
    catalog = load_json(Path(location) / ".claude-plugin" / "marketplace.json")
    plugins = catalog.get("plugins") or []
    return next((p for p in plugins if isinstance(p, dict) and p.get("name") == name), {})


def effective_manifest(root: Path, entry: dict) -> dict:
    """plugin.json when present, else the marketplace entry (which is then the manifest)."""
    path = root / ".claude-plugin" / "plugin.json"
    return load_json(path) if path.is_file() else dict(entry)


def replacing(root: Path, manifest: dict, key: str, default: str) -> list[Path]:
    """A replace-semantics key: the manifest's paths if set, else the default location."""
    return contained(root, manifest[key]) if key in manifest else [root / default]


def experimental_value(manifest: dict, key: str) -> tuple[bool, object]:
    """experimental.<key>, else the still-loading top-level <key>."""
    exp = manifest.get("experimental") or {}
    if isinstance(exp, dict) and key in exp:
        return True, exp[key]
    return (True, manifest[key]) if key in manifest else (False, None)


def enabled_plugins(paths: dict[str, Path]) -> dict[str, bool]:
    """Merged `enabledPlugins` maps, user then project then local; a later file wins per plugin.

    A plugin absent from every map is treated as enabled by the caller (`.get(name, True)`),
    which keeps today's behaviour for any install that predates the key.
    """
    merged: dict[str, bool] = {}
    for key in ENABLED_SOURCES:
        value = load_json(paths[key]).get("enabledPlugins") if key in paths else None
        if isinstance(value, dict):
            merged.update({str(k): v is True for k, v in value.items()})
    return merged


def plugin_dir_roots(paths: dict[str, Path]) -> list[Path]:
    """Plugins loaded from disk, not installed: CLAUDE_CODE_PLUGIN_DIRS (process env, else the
    env block of ~/.claude/settings.json, never a project's) and plugin folders auto-loaded from
    ~/.claude/skills/<name> and <project>/.claude/skills/<name>."""
    raw = os.environ.get("CLAUDE_CODE_PLUGIN_DIRS") or (
        load_json(paths["claude_global_settings"]).get("env") or {}
    ).get("CLAUDE_CODE_PLUGIN_DIRS", "")
    roots = [Path(p).expanduser() for p in str(raw).split(os.pathsep) if p.strip()]
    for skills in (paths["claude_global_skills"], paths["claude_proj_skills"]):
        if skills.is_dir():
            roots += [
                d
                for d in sorted(skills.iterdir())
                if (d / ".claude-plugin" / "plugin.json").is_file()
            ]
    seen: set[Path] = set()
    unique = []
    for r in roots:
        if r.is_dir() and r.resolve() not in seen:
            seen.add(r.resolve())
            unique.append(r)
    return unique


def cache_key(install: dict) -> str:
    """Changes whenever the installed copy changes: update, reinstall, or new commit."""
    return "|".join(
        str(install.get(k, "")) for k in ("installPath", "version", "gitCommitSha", "lastUpdated")
    )
