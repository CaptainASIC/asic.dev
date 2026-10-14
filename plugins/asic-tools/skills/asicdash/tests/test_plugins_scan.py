"""plugins_scan / plugin_manifest tests (PRP-027). Every input is a tmp_path tree; no ~/.claude.

A test that cannot fail is not a test: each case asserts the specific entry its fixture should
produce, and the negative half (what must NOT appear) where the behaviour is a filter.
"""

from __future__ import annotations

import json
from pathlib import Path

import plugin_manifest
import plugins_scan
import pytest
from plugin_manifest import marketplace_entry, plugin_dir_roots
from plugins_scan import scan_plugin_root, scan_plugins, scan_workflows


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No test measures cost (that shells out to `claude`), reads the real HOME or env dirs."""
    monkeypatch.setattr(plugins_scan, "plugin_costs", lambda keys: {})
    monkeypatch.setattr(plugin_manifest, "HOME", tmp_path)
    monkeypatch.delenv("CLAUDE_CODE_PLUGIN_DIRS", raising=False)


def make_plugin(base: Path, files: dict[str, str | dict | list]) -> Path:
    """Write a plugin tree under base; dict and list values are dumped as JSON."""
    base.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        path.write_text(text, encoding="utf-8")
    return base


def skill_md(name: str) -> str:
    return f"---\nname: {name}\ndescription: the {name} skill\n---\nbody\n"


def md(name: str) -> str:
    return f"---\nname: {name}\ndescription: {name} item\n---\nbody\n"


def hook(command: str) -> list[dict]:
    return [{"hooks": [{"type": "command", "command": command}]}]


def scan(root: Path, tmp_path: Path, entry: dict | None = None, registered: list | None = None):
    return scan_plugin_root(
        root,
        "p@m",
        "user",
        entry or {},
        None,
        tmp_path,
        registered if registered is not None else [],
    )


def of(entries: list, kind: str) -> list:
    return [e for e in entries if e.kind == kind]


def test_inline_manifest_hooks_scanned(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "cav",
        {
            ".claude-plugin/plugin.json": {
                "name": "cav",
                "hooks": {
                    "SessionStart": hook("sh ${CLAUDE_PLUGIN_ROOT}/a.sh"),
                    "UserPromptSubmit": hook("sh ${CLAUDE_PLUGIN_ROOT}/b.sh"),
                },
            }
        },
    )
    registered: list[str] = []
    hooks = of(scan(root, tmp_path, registered=registered), "hook")
    assert len(hooks) == 2
    assert f"sh {root}/a.sh" in registered and f"sh {root}/b.sh" in registered


def test_hook_file_and_manifest_path_merge(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            "hooks/hooks.json": {"hooks": {"Stop": hook("echo a")}},
            ".claude-plugin/plugin.json": {"name": "p", "hooks": "./extra.json"},
            "extra.json": {"hooks": {"Stop": hook("echo b")}},
        },
    )
    hooks = of(scan(root, tmp_path), "hook")
    assert {h.name for h in hooks} == {"echo a", "echo b"}
    assert len({h.source for h in hooks}) == 2


def test_entry_is_manifest_without_plugin_json(tmp_path: Path) -> None:
    market = tmp_path / "markets" / "m"
    make_plugin(
        market,
        {
            ".claude-plugin/marketplace.json": {
                "plugins": [
                    {
                        "name": "swift-lsp",
                        "description": "Swift language server",
                        "strict": False,
                        "lspServers": {
                            "sourcekit-lsp": {
                                "command": "sourcekit-lsp",
                                "extensionToLanguage": {".swift": "swift"},
                            }
                        },
                    }
                ]
            }
        },
    )
    make_plugin(
        tmp_path / ".claude" / "plugins",
        {"known_marketplaces.json": {"m": {"installLocation": str(market)}}},
    )
    root = make_plugin(tmp_path / "cache" / "swift-lsp", {"README.md": "readme"})
    entries = scan_plugin_root(
        root, "swift-lsp@m", "user", marketplace_entry("swift-lsp@m"), None, tmp_path, []
    )
    lsp = of(entries, "lsp")
    assert [e.name for e in lsp] == ["sourcekit-lsp"] and "swift" in lsp[0].desc
    assert entries[0].kind == "plugin" and entries[0].desc == "Swift language server"


def test_commands_key_replaces_default(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            "commands/a.md": md("a"),
            "extra/b.md": md("b"),
            ".claude-plugin/plugin.json": {"name": "p", "commands": ["./extra/b.md"]},
        },
    )
    assert [e.name for e in of(scan(root, tmp_path), "command")] == ["b"]


def test_commands_object_map(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {".claude-plugin/plugin.json": {"name": "p", "commands": {"deploy": {"content": "x"}}}},
    )
    cmds = of(scan(root, tmp_path), "command")
    assert [(c.name, c.desc) for c in cmds] == [("deploy", "inline content")]


def test_skills_key_adds_to_default(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            "skills/one/SKILL.md": skill_md("one"),
            "more/two/SKILL.md": skill_md("two"),
            ".claude-plugin/plugin.json": {"name": "p", "skills": ["./more/"]},
        },
    )
    assert {e.name for e in of(scan(root, tmp_path), "skill")} == {"one", "two"}


def test_paths_outside_root_dropped(tmp_path: Path) -> None:
    (tmp_path / "evil.md").write_text(md("evil"), encoding="utf-8")
    root = make_plugin(
        tmp_path / "p", {".claude-plugin/plugin.json": {"name": "p", "agents": ["../evil.md"]}}
    )
    assert of(scan(root, tmp_path), "agent") == []


def test_mod_detected_and_missing_is_broken(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p", {"hooks/hooks.json": {"modules": "./mod.ts"}, "hooks/mod.ts": "export {}"}
    )
    mods = of(scan(root, tmp_path), "mod")
    assert [(m.name, m.status) for m in mods] == [("mod.ts", "ok")]
    (root / "hooks" / "mod.ts").unlink()
    assert of(scan(root, tmp_path), "mod")[0].status.startswith("broken: missing")


def test_monitors_default_file_and_inline(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            "monitors/monitors.json": [
                {"name": "w", "command": "definitely-not-on-path-xyz", "description": "d"}
            ]
        },
    )
    mons = of(scan(root, tmp_path), "monitor")
    assert [m.name for m in mons] == ["w"] and "when: always" in mons[0].desc
    assert mons[0].status.startswith("broken:")
    make_plugin(
        root,
        {
            ".claude-plugin/plugin.json": {
                "name": "p",
                "experimental": {"monitors": [{"name": "i", "command": "sh"}]},
            }
        },
    )
    assert [m.name for m in of(scan(root, tmp_path), "monitor")] == ["i"]


def test_bin_and_plugin_settings_agent(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p", {"bin/tool": "#!/bin/sh\n", "settings.json": {"agent": "rev", "other": 1}}
    )
    entries = scan(root, tmp_path)
    assert [e.name for e in of(entries, "bin")] == ["1 executable(s)"]
    ps = of(entries, "plugin-settings")
    assert len(ps) == 1 and ps[0].desc.startswith("agent: rev") and "other" not in ps[0].name


def test_output_styles_and_themes_defaults(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p", {"output-styles/terse.md": md("terse"), "themes/dark.json": {"a": 1}}
    )
    entries = scan(root, tmp_path)
    assert [e.name for e in of(entries, "output-style")] == ["terse"]
    assert [e.name for e in of(entries, "theme")] == ["dark"]
    make_plugin(
        root,
        {"t2/light.json": {"a": 1}, ".claude-plugin/plugin.json": {"name": "p", "themes": "./t2/"}},
    )
    assert [e.name for e in of(scan(root, tmp_path), "theme")] == ["light"]


def _no_secret(entries: list, secret: str) -> None:
    for e in entries:
        for field in (e.name, e.source, e.desc, e.status):
            assert "?" not in field and secret not in field


def test_plugin_mcp_inline_map_redacted(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            ".claude-plugin/plugin.json": {
                "name": "p",
                "mcpServers": {"x": {"url": "https://h/p?token=SECRETT"}},
            }
        },
    )
    mcp = of(scan(root, tmp_path), "mcp")
    assert [m.name for m in mcp] == ["x"]
    _no_secret(mcp, "SECRETT")


def test_plugin_mcp_bundle_url_name_redacted(tmp_path: Path) -> None:
    root = make_plugin(
        tmp_path / "p",
        {
            ".claude-plugin/plugin.json": {
                "name": "p",
                "mcpServers": ["https://h/x.mcpb?token=SECRETB", "./b.mcpb"],
            }
        },
    )
    mcp = of(scan(root, tmp_path), "mcp")
    assert sorted(m.name for m in mcp) == ["b.mcpb", "x.mcpb"]
    _no_secret(mcp, "SECRETB")


def test_routing_regex_both_key_shapes(tmp_path: Path) -> None:
    wf = tmp_path / "wf"
    wf.mkdir()
    (wf / "w.js").write_text(
        "const ROUTING = {\n"
        "  bare: { model: 'sonnet', effort: 'low' },\n"
        "  'quoted-key': { model: 'opus', effort: 'high' },\n"
        "}\n",
        encoding="utf-8",
    )
    entries = scan_workflows([wf], "plugin:p")
    assert len(entries) == 1 and entries[0].desc.startswith("2 routing roles")


def _paths(tmp_path: Path, **over: Path) -> dict[str, Path]:
    keys = (
        "claude_installed_plugins",
        "claude_global_settings",
        "claude_global_settings_local",
        "claude_proj_settings",
        "claude_proj_settings_local",
        "claude_global_skills",
        "claude_proj_skills",
    )
    out = {k: tmp_path / "absent" / k for k in keys}
    out.update(over)
    return out


def test_plugin_dir_roots_env_and_skills_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_root = make_plugin(tmp_path / "dev", {".claude-plugin/plugin.json": {"name": "dev"}})
    skills = tmp_path / ".claude" / "skills"
    folder = make_plugin(skills / "sp", {".claude-plugin/plugin.json": {"name": "sp"}})
    make_plugin(skills / "plain", {"SKILL.md": skill_md("plain")})  # not a plugin folder
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_DIRS", f"{env_root}:{folder}")
    roots = plugin_dir_roots(_paths(tmp_path, claude_global_skills=skills))
    assert [r.resolve() for r in roots] == [env_root.resolve(), folder.resolve()]


def _installed(tmp_path: Path, plugins: dict[str, Path]) -> Path:
    data = {
        "version": 2,
        "plugins": {
            name: [{"scope": "user", "installPath": str(root), "version": "1.0.0"}]
            for name, root in plugins.items()
        },
    }
    path = tmp_path / "installed_plugins.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_from_disk_plugin_does_not_merge_with_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inst = make_plugin(tmp_path / "inst", {"skills/a/SKILL.md": skill_md("a")})
    disk = make_plugin(
        tmp_path / "disk",
        {"skills/b/SKILL.md": skill_md("b"), ".claude-plugin/plugin.json": {"name": "asic-tools"}},
    )
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_DIRS", str(disk))
    paths = _paths(tmp_path, claude_installed_plugins=_installed(tmp_path, {"asic-tools@m": inst}))
    entries = scan_plugins(paths, tmp_path, [])
    rows = [e for e in entries if e.kind == "plugin"]
    assert [r.name for r in rows] == ["asic-tools@m", "asic-tools (from disk)"]
    children = {
        r.name: {
            e.name
            for e in entries
            if e.scope == "plugin:" + r.name.split("@")[0] and e.kind == "skill"
        }
        for r in rows
    }
    assert children == {"asic-tools@m": {"a"}, "asic-tools (from disk)": {"b"}}


def test_disabled_plugin_row_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tree = {
        "hooks/hooks.json": {"modules": "./mod.ts"},
        "hooks/mod.ts": "export {}",
        "skills/a/SKILL.md": skill_md("a"),
    }
    roots = {n: make_plugin(tmp_path / n.split("@")[0], tree) for n in ("p1@m", "p2@m", "p3@m")}
    glob_settings = tmp_path / "settings.json"
    glob_settings.write_text(json.dumps({"enabledPlugins": {"p1@m": False, "p2@m": True}}))
    proj_local = tmp_path / "settings.local.json"
    proj_local.write_text(json.dumps({"enabledPlugins": {"p2@m": False}}))
    measured: list[dict] = []
    monkeypatch.setattr(plugins_scan, "plugin_costs", lambda keys: measured.append(keys) or {})
    paths = _paths(
        tmp_path,
        claude_installed_plugins=_installed(tmp_path, roots),
        claude_global_settings=glob_settings,
        claude_proj_settings_local=proj_local,
    )
    entries = scan_plugins(paths, tmp_path, [])
    for name in ("p1@m", "p2@m"):
        scope = "plugin:" + name.split("@")[0]
        rows = [e for e in entries if e.name == name]
        assert len(rows) == 1 and rows[0].status == "n/a: disabled" and rows[0].tokens == 0
        assert not [e for e in entries if e.scope == scope]
        assert all(name not in keys for keys in measured)
    assert {e.kind for e in entries if e.scope == "plugin:p3"} >= {"mod", "skill"}
