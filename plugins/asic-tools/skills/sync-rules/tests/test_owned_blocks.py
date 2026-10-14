"""Tests for owned_blocks.py.

Function tests pin compose()'s byte-exact join (it must match graphify's own append, or the two tools
rewrite each other's file on every run); CLI tests drive the script by subprocess, the contract
SKILL.md tells the agent to run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "owned_blocks.py"
sys.path.insert(0, str(SCRIPT.parent))

from owned_blocks import compose


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the helper CLI."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        # Reason: the exit code IS the assertion here, so a nonzero must return, never raise.
        check=False,
    )


def test_compose_without_target_block_is_source() -> None:
    """Expected: a target with no owned block composes to the source unchanged."""
    assert compose("A\n", "A\n") == "A\n"


def test_compose_appends_block_like_graphify() -> None:
    """Expected: the composed text is byte-identical to graphify's own append."""
    target = "A\n\n# graphify\n- **graphify** (x) - y\nWhen …\n"
    assert compose("A\n", target) == target


def test_mid_file_block_moves_to_eof_and_keeps_following_sections() -> None:
    """Edge: a legacy mid-file block moves to EOF and never drags the next H2 with it."""
    target = "A\n\n# graphify\nreg\n\n## Self-test\nS\n"
    composed = compose("A\n\n## Self-test\nS\n", target)
    assert composed == "A\n\n## Self-test\nS\n\n# graphify\nreg\n"
    assert composed.count("## Self-test") == 1


def test_marker_must_be_whole_line() -> None:
    """Edge: `# graphify` inside a sentence is not a marker; nothing is extracted."""
    target = "A\n- see `# graphify` docs\n"
    assert compose("A\n", target) == "A\n"


def test_cli_missing_target_composes_source(tmp_path: Path) -> None:
    """Expected: an absent target composes to the source (first install)."""
    source = tmp_path / "src.md"
    source.write_text("Rules\n", encoding="utf-8")
    result = run("compose", str(source), str(tmp_path / "absent.md"))
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Rules\n"


def test_cli_usage_error_exits_two() -> None:
    """Failure: a wrong argument count exits 2 with a usage line."""
    result = run("compose")
    assert result.returncode == 2
    assert "usage" in result.stderr
