"""asicdash plugin scanning: one plugin root -> every component Claude Code loads from it.

Split out of scanners.py (PRP-027). Imports helpers from scanners, plugin_manifest and
plugin_cost; scanners never imports this module (the PRP-018 one-way rule, one level further). Resolution follows
code.claude.com/docs/en/plugins-reference, read against Claude Code 2.1.296:

- replaces its default: commands, agents, outputStyles, workflows, experimental.themes,
  experimental.monitors (top-level `themes` / `monitors` still load)
- adds to its default: skills
- merges with its default: hooks, mcpServers, lspServers

A plugin with no .claude-plugin/plugin.json takes its marketplace entry as the manifest (both
installed LSP plugins are this shape). Not modelled, on purpose (no installed plugin needs it):
a strict entry appending components to a plugin.json, and the strict:false conflict error.

Inventory only. Context cost is measured by plugin_cost (`claude plugin details`), never estimated.
Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from plugin_manifest import (
    as_list,
    cache_key,
    contained,
    effective_manifest,
    enabled_plugins,
    experimental_value,
    load_array,
    marketplace_entry,
    plugin_dir_roots,
    replacing,
)
from scanners import (
    Entry,
    command_label,
    command_status,
    flatten_hooks,
    load_json,
    mcp_desc,
    read_text,
    scan_md_dir,
    scan_skills,
    short,
)

# --- moved VERBATIM from scanners.py (PRP-018), including this CRITICAL comment -----------------
# A plugin workflow's model/effort lives in a named ROUTING block (PRP-014). Read that block with
# a regex over one agreed convention -- never a JS parser.
# CRITICAL: the two shipped blocks use DIFFERENT key shapes. review_workflow.js writes bare
# identifiers (`reviewLogic:`), improve_workflow.js writes quoted keys
# (`'version-consolidation':`). The optional ["']? is what accepts both; a regex matching only one
# reports 0 roles on a file that plainly has six, silently.
ROUTING_BLOCK = re.compile(r"const\s+ROUTING\s*=\s*\{(.*?)\n\}", re.DOTALL)
ROUTING_ROLE = re.compile(
    r"""["']?(?P<role>[\w-]+)["']?\s*:\s*\{[^}]*?model:\s*['"](?P<model>[\w-]+)['"]"""
    r"""(?:[^}]*?effort:\s*['"](?P<effort>[\w-]+)['"])?""",
    re.DOTALL,
)
META_NAME = re.compile(r"name:\s*['\"]([\w-]+)['\"]")


def plugin_costs(keys: dict[str, str]) -> dict:
    """Task 3 stub: no cost measurement yet (Task 4 replaces it with plugin_cost.plugin_costs)."""
    return {}


def _md_entries(paths: list[Path], kind: str, scope: str) -> list[Entry]:
    """Directories scan recursively; a single .md file yields its one entry."""
    out: list[Entry] = []
    for p in paths:
        if p.is_dir():
            out += scan_md_dir(p, kind, scope)
        elif p.is_file() and p.suffix == ".md":
            out += [e for e in scan_md_dir(p.parent, kind, scope) if e.source == short(p)]
    return out


def scan_plugin_skills(root: Path, manifest: dict, scope: str) -> list[Entry]:
    """Default skills/ plus manifest paths (adds). A path may hold <name>/SKILL.md folders or be
    one skill folder itself; a plugin with only a root SKILL.md is a single skill."""
    paths = [root / "skills"] + contained(root, manifest.get("skills"))
    out: list[Entry] = []
    for p in paths:
        if (p / "SKILL.md").is_file() and p != root / "skills":
            out += [e for e in scan_skills(p.parent, scope) if e.source == short(p / "SKILL.md")]
        else:
            out += scan_skills(p, scope)
    if not out and "skills" not in manifest and (root / "SKILL.md").is_file():
        out += [e for e in scan_skills(root.parent, scope) if e.source == short(root / "SKILL.md")]
    return out


def scan_plugin_commands(root: Path, manifest: dict, scope: str) -> list[Entry]:
    """commands: path(s) replace the default; an object map names commands directly."""
    value = manifest.get("commands")
    if isinstance(value, dict):
        return [
            Entry(
                "claude",
                "command",
                name,
                scope,
                short(root / ".claude-plugin"),
                desc="inline content"
                if isinstance(cfg, dict) and "content" in cfg
                else f"source: {cfg.get('source', '')}"
                if isinstance(cfg, dict)
                else "",
            )
            for name, cfg in sorted(value.items())
        ]
    return _md_entries(replacing(root, manifest, "commands", "commands"), "command", scope)


def scan_plugin_hooks(
    root: Path, manifest: dict, scope: str, project: Path, registered: list[str]
) -> list[Entry]:
    """hooks/hooks.json, then each manifest hooks value (file path or inline event map), merged."""
    default = root / "hooks" / "hooks.json"
    manifest_src = root / ".claude-plugin" / "plugin.json"
    sources: list[tuple[dict, str]] = []
    if default.is_file():
        sources.append((load_json(default).get("hooks") or {}, short(default)))
    for item in as_list(manifest.get("hooks")):
        if isinstance(item, dict):  # GOTCHA: inline value is the bare event map, no wrapper
            sources.append(
                (item, short(manifest_src) if manifest_src.is_file() else "marketplace entry")
            )
        elif isinstance(item, str):
            sources += [(load_json(p).get("hooks") or {}, short(p)) for p in contained(root, item)]
    out: list[Entry] = []
    for event_map, src in sources:
        for cmd, events in sorted(flatten_hooks(event_map).items()):
            registered.append(cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(root)))
            out.append(
                Entry(
                    "claude",
                    "hook",
                    command_label(cmd),
                    scope,
                    src,
                    desc=f"{len(events)} event(s): " + ", ".join(events),
                    status=command_status(cmd, project, plugin_root=root),
                )
            )
    return out


def scan_plugin_mods(root: Path, scope: str) -> list[Entry]:
    """A mod: hooks/hooks.json names a hooks module under `modules`, relative to hooks/."""
    hooks_file = root / "hooks" / "hooks.json"
    out: list[Entry] = []
    for mod in as_list(load_json(hooks_file).get("modules")):
        if not isinstance(mod, str):
            continue
        path = (hooks_file.parent / mod).resolve()
        out.append(
            Entry(
                "claude",
                "mod",
                path.name,
                scope,
                short(hooks_file),
                desc="hooks module: in-process, unsandboxed function hooks",
                status="ok" if path.is_file() else f"broken: missing {short(path)}",
            )
        )
    return out


def _server_maps(
    root: Path, manifest: dict, key: str, default: str
) -> list[tuple[str, object, str]]:
    """(name, config, source) for mcpServers / lspServers: default file first, then the manifest
    (merge semantics; a later name replaces an earlier one). A file may wrap its map in the key."""
    found: dict[str, tuple[object, str]] = {}

    def add(mapping: object, src: str) -> None:
        if isinstance(mapping, dict):
            inner = mapping.get(key, mapping)
            if isinstance(inner, dict):
                for name, cfg in inner.items():
                    found[name] = (cfg, src)

    if (root / default).is_file():
        add(load_json(root / default), short(root / default))
    for item in as_list(manifest.get(key)):
        if isinstance(item, dict):
            add(item, "manifest")
        elif isinstance(item, str) and item.endswith(".json"):
            for p in contained(root, item):
                add(load_json(p), short(p))
        elif isinstance(item, str):  # .mcpb / .dxt bundle path or URL
            # CRITICAL: the name is built from the URL PATH only. Path(item).name on
            # "https://h/x.mcpb?token=S" is "x.mcpb?token=S" and would leak the key via `name`.
            found[Path(urlsplit(item).path).name or "bundle"] = ({"url": item}, "manifest bundle")
    return [(n, cfg, src) for n, (cfg, src) in sorted(found.items())]


def scan_plugin_servers(root: Path, manifest: dict, scope: str) -> list[Entry]:
    """Plugin MCP servers (redacted desc) and LSP servers (command + languages)."""
    out = [
        Entry("claude", "mcp", n, scope, src, desc=mcp_desc(cfg))
        for n, cfg, src in _server_maps(root, manifest, "mcpServers", ".mcp.json")
    ]
    for n, cfg, src in _server_maps(root, manifest, "lspServers", ".lsp.json"):
        c = cfg if isinstance(cfg, dict) else {}
        langs = ", ".join(sorted(set((c.get("extensionToLanguage") or {}).values())))
        out.append(
            Entry(
                "claude", "lsp", n, scope, src, desc=f"{c.get('command', '')} · {langs}".strip(" ·")
            )
        )
    return out


def scan_plugin_extras(root: Path, manifest: dict, scope: str, project: Path) -> list[Entry]:
    """Output styles, themes, monitors, bin/ executables, plugin settings."""
    out = _md_entries(
        replacing(root, manifest, "outputStyles", "output-styles"), "output-style", scope
    )
    found, value = experimental_value(manifest, "themes")
    theme_paths = contained(root, value) if found else [root / "themes"]
    for p in theme_paths:
        files = sorted(p.glob("*.json")) if p.is_dir() else ([p] if p.is_file() else [])
        out += [Entry("claude", "theme", f.stem, scope, short(f)) for f in files]
    found, value = experimental_value(manifest, "monitors")
    if isinstance(value, list):
        monitors, src = value, "manifest"
    else:
        path = (
            contained(root, value)[0]
            if found and contained(root, value)
            else (root / "monitors" / "monitors.json")
        )
        monitors, src = load_array(path), short(path)
    for m in monitors:
        if isinstance(m, dict) and m.get("name"):
            out.append(
                Entry(
                    "claude",
                    "monitor",
                    str(m["name"]),
                    scope,
                    src,
                    desc=f"{m.get('description', '')} · when: {m.get('when', 'always')}",
                    status=command_status(str(m.get("command", "")), project, root),
                )
            )
    bin_dir = root / "bin"
    if bin_dir.is_dir():
        files = sorted(f.name for f in bin_dir.iterdir() if f.is_file())
        if files:
            out.append(
                Entry(
                    "claude",
                    "bin",
                    f"{len(files)} executable(s)",
                    scope,
                    short(bin_dir),
                    desc="on the Bash PATH while enabled: " + ", ".join(files[:8]),
                )
            )
    settings_file = root / "settings.json"  # takes precedence over manifest["settings"]
    settings = (
        load_json(settings_file) if settings_file.is_file() else (manifest.get("settings") or {})
    )
    kept = {k: settings[k] for k in ("agent", "subagentStatusLine") if k in settings}
    if kept:
        desc = (
            f"agent: {kept['agent']} — the main thread runs as this agent while enabled"
            if "agent" in kept
            else "subagentStatusLine set"
        )
        out.append(
            Entry(
                "claude",
                "plugin-settings",
                ", ".join(kept),
                scope,
                short(settings_file) if settings_file.is_file() else "manifest",
                desc=desc,
            )
        )
    return out


def scan_workflows(paths: list[Path], scope: str) -> list[Entry]:
    """Plugin workflows, with the model/effort each routing role sets.

    Reports the role COUNT alongside the models so a block that parsed to nothing shows
    `0 routing roles` next to a file that plainly has them -- a loud discrepancy, not a blank.
    """
    entries: list[Entry] = []
    files = [
        f
        for p in paths
        for f in (sorted(p.glob("*.js")) if p.is_dir() else [p])
        if f.is_file() and f.suffix == ".js"
    ]
    for f in files:
        text = read_text(f)
        block = ROUTING_BLOCK.search(text)
        roles = ROUTING_ROLE.findall(block.group(1)) if block else []
        name_m = META_NAME.search(text)
        combos: dict[str, int] = {}
        for _role, model, effort in roles:
            key = f"{model}·{effort}" if effort else model
            combos[key] = combos.get(key, 0) + 1
        detail = ", ".join(f"{k} ×{v}" for k, v in sorted(combos.items()))
        plural = "" if len(roles) == 1 else "s"
        desc = f"{len(roles)} routing role{plural}" + (f": {detail}" if detail else "")
        entries.append(
            Entry(
                tool="claude",
                kind="workflow",
                name=name_m.group(1) if name_m else f.stem,
                scope=scope,
                source=short(f),
                desc=desc,
            )
        )
    return entries


def _cost_prefix(cost: tuple[dict | None, str] | None) -> str:
    """Plugin-row desc prefix: the measured cost, or why it is missing."""
    if cost is None:
        return ""
    measured, reason = cost
    if not measured:
        return f"cost n/a ({reason}) — "  # anchor: attention_of tests startswith "cost n/a ("
    heavy = sorted(measured["components"], key=lambda c: -c["on_invoke"])[:2]
    tail = ", ".join(f"{c['component']} ~{c['on_invoke'] / 1000:.1f}k" for c in heavy)
    return (
        f"~{measured['always_on']:,} tok always-on"
        + (f" · heaviest on invoke: {tail}" if tail else "")
        + " — "
    )


def scan_plugin_root(
    root: Path,
    full_name: str,
    install_scope: str,
    entry: dict,
    cost: tuple[dict | None, str] | None,
    project: Path,
    registered: list[str],
) -> list[Entry]:
    """The plugin row plus every component under one plugin root."""
    scope = f"plugin:{full_name.split('@')[0]}"
    if not root.is_dir():
        return [
            Entry(
                "claude",
                "plugin",
                full_name,
                install_scope,
                short(root),
                status="broken: install path missing",
            )
        ]
    manifest = effective_manifest(root, entry)
    # GOTCHA: like `claude plugin details`, prefer the entry's description, filling from plugin.json.
    desc = entry.get("description") or manifest.get("description", "")
    row = Entry(
        "claude", "plugin", full_name, install_scope, short(root), desc=_cost_prefix(cost) + desc
    )
    if cost and cost[0]:
        row.tokens = int(cost[0]["always_on"])
    return [
        row,
        *scan_plugin_skills(root, manifest, scope),
        *scan_plugin_commands(root, manifest, scope),
        *_md_entries(replacing(root, manifest, "agents", "agents"), "agent", scope),
        *scan_workflows(replacing(root, manifest, "workflows", "workflows"), scope),
        *scan_plugin_hooks(root, manifest, scope, project, registered),
        *scan_plugin_mods(root, scope),
        *scan_plugin_servers(root, manifest, scope),
        *scan_plugin_extras(root, manifest, scope, project),
    ]


def scan_plugins(paths: dict[str, Path], project: Path, registered: list[str]) -> list[Entry]:
    """Every enabled installed plugin (with harness-measured cost), each disabled one as a bare
    `n/a: disabled` row, then every from-disk plugin."""
    data = load_json(paths["claude_installed_plugins"])
    installed = []
    for full_name, installs in sorted((data.get("plugins") or {}).items()):
        install = installs[0] if isinstance(installs, list) and installs else {}
        installed.append((full_name, install, Path(install.get("installPath", "/nonexistent"))))
    enabled = enabled_plugins(paths)
    costs = plugin_costs(
        {n: cache_key(i) for n, i, root in installed if root.is_dir() and enabled.get(n, True)}
    )
    entries: list[Entry] = []
    for full_name, install, root in installed:
        if not enabled.get(full_name, True):
            # Reason: a disabled plugin loads nothing. Row only: no children (so no mod, monitor
            # or agent flag), no cost measurement, tokens 0; "n/a" keeps it out of counts.
            entries.append(
                Entry(
                    "claude",
                    "plugin",
                    full_name,
                    install.get("scope", "user"),
                    short(root),
                    desc="disabled in enabledPlugins",
                    status="n/a: disabled",
                )
            )
            continue
        entries += scan_plugin_root(
            root,
            full_name,
            install.get("scope", "user"),
            marketplace_entry(full_name),
            costs.get(full_name),
            project,
            registered,
        )
    for root in plugin_dir_roots(paths):
        manifest_name = load_json(root / ".claude-plugin" / "plugin.json").get("name") or root.name
        # Reason: a from-disk copy of an installed plugin must not share its scope key. The row
        # name carries the marker, so scope_of(row) == "plugin:<name> (from disk)" and
        # html_report groups children by that exact scope with no change.
        entries += scan_plugin_root(
            root,
            f"{manifest_name} (from disk)",
            "from disk",
            {},
            (None, "not an installed plugin"),
            project,
            registered,
        )
    return entries
