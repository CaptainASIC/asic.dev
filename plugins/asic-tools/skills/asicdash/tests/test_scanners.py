"""scanners / settings_risk / attention tests (PRP-027). Inputs live in tmp_path; no ~/.claude."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scanners import redact_url, scan_mcp


def test_redact_url_drops_query_and_userinfo() -> None:
    out = redact_url("https://u:p@api.example.com/mcp?apiKey=SECRET#f")
    assert out == "https://api.example.com/mcp (redacted)"
    assert "SECRET" not in out and "u:p" not in out


def test_redact_url_masks_token_in_path() -> None:
    out = redact_url("https://mcp.example.com/s/abcdEFGH1234ijklMNOP5678qr/mcp")
    assert out == "https://mcp.example.com/s/[…]/mcp (redacted)"
    assert "abcdEFGH1234ijklMNOP5678qr" not in out
    assert redact_url("https://h/mcp") == "https://h/mcp"


def test_redact_url_passes_non_urls_through() -> None:
    for value in ("npx", "stdio", ""):
        assert redact_url(value) == value


def test_redact_url_unparseable_port() -> None:
    assert redact_url("http://h:99999/x") == "<unparseable url>"


def _paths(tmp_path: Path, **files: Path) -> dict[str, Path]:
    """A known_paths()-shaped dict whose keys all point at absent tmp files unless overridden."""
    keys = (
        "claude_user_state",
        "claude_proj_mcp",
        "claude_global_settings",
        "claude_global_settings_local",
        "claude_proj_settings",
        "claude_proj_settings_local",
    )
    out = {k: tmp_path / f"absent-{k}.json" for k in keys}
    out.update(files)
    return out


def test_scan_mcp_never_emits_query_strings(tmp_path: Path) -> None:
    mcp = tmp_path / ".mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"r": {"url": "https://h/mcp?key=SECRETV"}}}))
    entries = scan_mcp(_paths(tmp_path, claude_proj_mcp=mcp), tmp_path)
    assert entries, "the project server must be reported"
    for e in entries:
        for field in (e.name, e.source, e.desc, e.status):
            assert "?" not in field and "SECRETV" not in field


# --- settings risk (settings_risk.py) -----------------------------------------------------------

from scanners import scan_md_dir, scan_settings
from settings_risk import broad_allows, scan_process_env, scan_settings_risk


def test_broad_allows_flags_each_doc_category() -> None:
    rules = [
        "Bash",
        "Bash(*)",
        "PowerShell(*)",
        "Bash(python*)",
        "Bash(python3 *)",
        "Bash(python3:*)",
        "Bash(npm run *)",
        "Bash(uvx *)",
        "Agent",
        "Monitor(*)",
    ]
    assert broad_allows(rules) == rules


def test_broad_allows_ignores_narrow_rules() -> None:
    narrow = [
        "Bash(npm test)",
        "Bash(git status *)",
        "Bash(uv run pytest *)",
        "Agent(Explore)",
        'Bash(python3 "/abs/asicdash.py" --json)',
    ]
    assert broad_allows(narrow) == []


def test_scan_settings_risk_emits_broad_allow_entry(tmp_path: Path) -> None:
    proj = tmp_path / "settings.json"
    proj.write_text(json.dumps({"permissions": {"allow": ["Bash(python3 *)", "Read"]}}))
    paths = _paths(tmp_path, claude_proj_settings=proj)
    risk = scan_settings_risk(paths)
    assert len(risk) == 1 and risk[0].kind == "permissions" and risk[0].scope == "project"
    assert risk[0].desc.startswith("broad allow: ")
    plain = scan_settings(proj, "project", tmp_path, [])
    assert not [e for e in plain if e.desc.startswith("broad allow: ")]


def test_routing_env_in_settings_names_only(tmp_path: Path) -> None:
    glob = tmp_path / "settings.json"
    glob.write_text(json.dumps({"env": {"CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "v-123", "FOO": "x"}}))
    risk = scan_settings_risk(_paths(tmp_path, claude_global_settings=glob))
    assert [e.name for e in risk] == ["routing override: CLAUDE_CODE_SUBAGENT_MODEL_FORCE"]
    for e in risk:
        for field in (e.name, e.source, e.desc, e.status):
            assert "v-123" not in field


def test_scan_process_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("CLAUDE_CODE_SUBAGENT_MODEL_FORCE", "CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SUBAGENT_MODEL", raising=False)
    assert scan_process_env() == []
    monkeypatch.setenv("CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL", "haiku")
    assert [e.name for e in scan_process_env()] == [
        "routing override: CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL"
    ]
    monkeypatch.delenv("CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL")
    monkeypatch.setenv("CLAUDE_CODE_SUBAGENT_MODEL", "sonnet")
    info = scan_process_env()
    assert len(info) == 1 and not info[0].name.startswith("routing override: ")


def test_paths_rule_is_conditional(tmp_path: Path) -> None:
    (tmp_path / "py.md").write_text("---\npaths:\n  - src/**/*.py\n---\n" + "x" * 400)
    (tmp_path / "inline.md").write_text('---\npaths: "**/*.py"\n---\n' + "z" * 400)
    (tmp_path / "core.md").write_text("# always\n" + "y" * 400)
    e = {x.name: x for x in scan_md_dir(tmp_path, "rule", "global", autoloaded=True)}
    for name in ("py", "inline"):
        assert e[name].tokens == 0 and e[name].desc.startswith("conditional (paths)")
    assert e["core"].tokens > 0
