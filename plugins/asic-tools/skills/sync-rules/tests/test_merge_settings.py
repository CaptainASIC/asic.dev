"""Tests for merge_settings.py.

Driven by subprocess against the CLI, because the CLI is the contract the SKILL tells the agent to
run — mirroring prp-implement/tests/test_prp_status.py. Every exit-code assertion also asserts the
script's own message: a bare ``returncode == 2`` also matches python's "can't open file".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPT = SKILL / "scripts" / "merge_settings.py"
FRAGMENT = SKILL.parent.parent / "rules" / "settings.fragment.json"


def run(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the merger against ``target`` with the bundled fragment."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--fragment", str(FRAGMENT), "--target", str(target), *args],
        capture_output=True,
        text=True,
        # Reason: the exit code IS the assertion here, so a nonzero must return, never raise.
        check=False,
    )


def test_absent_target_is_created_then_current(tmp_path: Path) -> None:
    """Expected: an absent settings.json is created and a second run reports current."""
    target = tmp_path / "settings.json"
    first = run(target, "--write")
    assert first.returncode == 0
    assert "STATUS: pending" in first.stdout and "WROTE:" in first.stdout
    data = json.loads(target.read_text())
    assert data["attribution"] == {"commit": "", "pr": "", "sessionUrl": False}
    assert "Bash(git push *)" in data["permissions"]["deny"]
    assert data["autoMode"]["hard_deny"][0] == "$defaults"
    again = run(target)
    assert again.returncode == 0 and "STATUS: current" in again.stdout


def test_unrelated_keys_and_list_order_survive(tmp_path: Path) -> None:
    """Expected: keys the fragment never mentions are untouched; lists only gain items."""
    target = tmp_path / "settings.json"
    target.write_text(
        json.dumps({"model": "opus", "permissions": {"deny": ["Bash(rm -rf *)"], "allow": ["X"]}})
    )
    result = run(target, "--write")
    assert result.returncode == 0
    data = json.loads(target.read_text())
    assert data["model"] == "opus"
    assert data["permissions"]["allow"] == ["X"]
    assert data["permissions"]["deny"] == ["Bash(rm -rf *)", "Bash(git push *)"]
    assert (tmp_path / "settings.json.sync-rules.bak").exists()


def test_attribution_false_satisfies_fragment(tmp_path: Path) -> None:
    """Edge: attribution=false already hides everything and is never rewritten or flagged."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"attribution": False}))
    result = run(target, "--write")
    assert result.returncode == 0 and "CONFLICT" not in result.stdout
    assert json.loads(target.read_text())["attribution"] is False


def test_scalar_conflict_kept_unless_preferred(tmp_path: Path) -> None:
    """Edge: a differing scalar is reported and kept; --prefer-fragment replaces it."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"attribution": {"commit": "Signed-off-by: me"}}))
    kept = run(target, "--write")
    assert "STATUS: conflict" in kept.stdout and "attribution.commit" in kept.stdout
    assert json.loads(target.read_text())["attribution"]["commit"] == "Signed-off-by: me"
    run(target, "--write", "--prefer-fragment")
    assert json.loads(target.read_text())["attribution"]["commit"] == ""


def test_owned_hard_deny_list_is_a_conflict(tmp_path: Path) -> None:
    """Edge: a hard_deny list without "$defaults" is never silently given the defaults back."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"autoMode": {"hard_deny": ["Never deploy"]}}))
    result = run(target, "--write")
    assert "STATUS: conflict" in result.stdout and "$defaults" in result.stdout
    assert json.loads(target.read_text())["autoMode"]["hard_deny"] == ["Never deploy"]


def test_dry_run_never_writes(tmp_path: Path) -> None:
    """Expected: without --write the target is byte-identical afterwards."""
    target = tmp_path / "settings.json"
    target.write_text('{"model": "opus"}\n')
    result = run(target)
    assert result.returncode == 0 and "STATUS: pending" in result.stdout
    assert target.read_text() == '{"model": "opus"}\n'


def test_invalid_json_fails_without_writing(tmp_path: Path) -> None:
    """Failure: unparseable settings exit 2 with the path named, and are left untouched."""
    target = tmp_path / "settings.json"
    target.write_text('{"model": ')
    result = run(target, "--write")
    assert result.returncode == 2 and "invalid JSON" in result.stderr
    assert target.read_text() == '{"model": '


def test_non_object_top_level_fails(tmp_path: Path) -> None:
    """Failure: a JSON array at the top level is refused."""
    target = tmp_path / "settings.json"
    target.write_text("[1]")
    result = run(target)
    assert result.returncode == 2 and "not a JSON object" in result.stderr


GREP_SH = "bash '/Users/x/.claude/hooks/graphify-grep-guard.sh'"
READ_SH = "bash '/Users/x/.claude/hooks/graphify-read-guard.sh'"


def _group(matcher: str, *commands: str) -> dict:
    """Build one PreToolUse hook group."""
    return {"matcher": matcher, "hooks": [{"type": "command", "command": c} for c in commands]}


def _run_with(fragment: dict, target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the merger with an ad-hoc fragment written beside the target."""
    path = target.parent / "fragment.json"
    path.write_text(json.dumps(fragment))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--fragment", str(path), "--target", str(target), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_retire_removes_only_matching_hook_entries(tmp_path: Path) -> None:
    """Expected: a retired command leaves; an unrelated entry in the same group stays."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"hooks": {"PreToolUse": [_group("Bash", GREP_SH, "echo keep")]}}))
    result = _run_with(
        {"$retire": {"hooks.PreToolUse": ["graphify-grep-guard.sh"]}}, target, "--write"
    )
    assert result.returncode == 0, result.stderr
    assert f"RETIRED: {GREP_SH}" in result.stdout
    groups = json.loads(target.read_text())["hooks"]["PreToolUse"]
    assert groups == [_group("Bash", "echo keep")]


def test_retire_drops_emptied_group_and_appends_new_groups(tmp_path: Path) -> None:
    """Expected: the live shape becomes exactly the fragment's two groups; others survive."""
    target = tmp_path / "settings.json"
    other = _group("Write", "echo other")
    live = [_group("Bash", GREP_SH), other, _group("Read|Glob", READ_SH)]
    target.write_text(json.dumps({"hooks": {"PreToolUse": live}}))
    result = run(target, "--write")
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("RETIRED:") == 2
    groups = json.loads(target.read_text())["hooks"]["PreToolUse"]
    fragment = json.loads(FRAGMENT.read_text())["hooks"]["PreToolUse"]
    assert groups == [other, *fragment]


def test_retire_then_rerun_is_current(tmp_path: Path) -> None:
    """Edge: after a write, a second dry-run has nothing to retire and reports current."""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"hooks": {"PreToolUse": [_group("Bash", GREP_SH)]}}))
    first = run(target, "--write")
    assert f"RETIRED: {GREP_SH}" in first.stdout
    again = run(target)
    assert again.returncode == 0 and "STATUS: current" in again.stdout
    assert "RETIRED:" not in again.stdout


def test_retire_key_never_written_to_target(tmp_path: Path) -> None:
    """Edge: the fragment's `$retire` instruction is consumed, never copied into settings."""
    assert "$retire" in json.loads(FRAGMENT.read_text())
    target = tmp_path / "settings.json"
    run(target, "--write")
    assert "$retire" not in json.loads(target.read_text())


def test_retire_unknown_path_exits_two(tmp_path: Path) -> None:
    """Failure: retiring anything but hooks.PreToolUse is refused and nothing is written."""
    target = tmp_path / "settings.json"
    target.write_text('{"permissions": {"allow": ["x"]}}\n')
    result = _run_with({"$retire": {"permissions.allow": ["x"]}}, target, "--write")
    assert result.returncode == 2 and "$retire" in result.stderr
    assert target.read_text() == '{"permissions": {"allow": ["x"]}}\n'
