"""scanners / settings_risk / attention tests (PRP-027). Inputs live in tmp_path; no ~/.claude."""

from __future__ import annotations

import json
from pathlib import Path

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
