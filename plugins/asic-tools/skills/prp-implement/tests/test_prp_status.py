"""Tests for prp_status.py.

Driven by subprocess against the CLI, because the CLI is the contract the SKILL tells the agent to
run — mirroring test_validate_okf.py.

Every exit-code assertion also asserts the script's own message. A bare ``returncode == 2`` also
matches python's "can't open file" when the script is absent, so a code-only check would pass with
no script at all — a test that cannot fail.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prp_status.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run(target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the linter against a directory and capture its output."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target), *args],
        capture_output=True,
        text=True,
        # Reason: the exit code IS the assertion here, so a nonzero must return, never raise.
        check=False,
    )


def case(name: str) -> Path:
    """Return a nonconformant fixture directory by case name."""
    return FIXTURES / "nonconformant" / name


# ── expected use ────────────────────────────────────────────────────────────────────────────


def test_conformant_corpus_exits_zero() -> None:
    """Expected: every enum value, plus an em-dash note, passes."""
    result = run(FIXTURES / "conformant")
    assert result.returncode == 0
    assert "FAIL" not in result.stderr


def test_each_enum_value_is_classified() -> None:
    """Expected: all five values render with their own glyph, none as INVALID."""
    result = run(FIXTURES / "conformant")
    assert result.returncode == 0
    assert "INVALID" not in result.stdout
    for value in ("Draft", "Ready for execution", "Implemented", "Blocked", "Superseded"):
        assert value in result.stdout


def test_em_dash_note_is_kept_and_not_linted() -> None:
    """Edge: prose after an em dash is captured verbatim and never judged."""
    result = run(FIXTURES / "conformant")
    assert result.returncode == 0
    assert "Snyk gate waived" in result.stdout


def test_draft_with_em_dash_note_is_conformant() -> None:
    """Edge: `Draft — awaiting review` is conformant — the prefix is the enum, the note is prose.

    Listed in §2.2 as deliberately NOT a non-conforming shape. Treating it as one would reject a
    valid status because its suffix looked unusual.
    """
    result = run(FIXTURES / "conformant")
    assert result.returncode == 0
    assert "awaiting review" in result.stdout


def test_counts_header_matches_row_count() -> None:
    """Edge: the counts header is derived from the rows, so it cannot disagree with the table."""
    result = run(FIXTURES / "conformant")
    rows = [ln for ln in result.stdout.splitlines() if ln.startswith("| 0")]
    assert f"**Total PRPs:** {len(rows)}" in result.stdout


# ── the enum: every non-conforming shape is rejected ────────────────────────────────────────


def test_non_conforming_spellings_rejected() -> None:
    """Failure: each real-world non-conforming spelling exits 1 and is named."""
    for name in (
        "complete",
        "planned",
        "proposed",
        "implemented_tested",
        "draft_dated",
        "superseded_caps",
        "implemented_prose",
        "us_date",
        "placeholder_date",
        "lowercase",
    ):
        result = run(case(name))
        assert result.returncode == 1, name
        assert "FAIL" in result.stderr, name
    # the literal shape, not only the fixture alias, so a renamed fixture cannot hide the case
    assert "Implemented and tested" in run(case("implemented_tested")).stderr


def test_case_must_match_exactly() -> None:
    """Failure: prp-implement matches the value literally, so a tolerant linter would mislead."""
    result = run(case("lowercase"))
    assert result.returncode == 1
    assert "non-conforming status" in result.stderr


# ── the false accepts ───────────────────────────────────────────────────────────────────────


def test_regex_shaped_non_date_rejected() -> None:
    """Failure: 2026-00-00 matches the pattern and is not a calendar date."""
    result = run(case("impossible_date"))
    assert result.returncode == 1
    assert "2026-00-00" in result.stderr
    assert "date" in result.stderr


def test_missing_status_is_violation_not_indeterminate() -> None:
    """Failure: an absent required field is never excused as a parser limitation."""
    result = run(case("no_status"))
    assert result.returncode == 1, "a missing Status must be 1, never 3"
    assert "no `**Status:**` line" in result.stderr


def test_bare_implemented_rejected() -> None:
    """Failure: Implemented with no date names the date rule."""
    result = run(case("implemented_bare"))
    assert result.returncode == 1
    assert "date on Implemented" in result.stderr


def test_dangling_successor_rejected() -> None:
    """Failure: a successor pointer to a PRP that does not exist is a missing successor."""
    result = run(case("dangling_successor"))
    assert result.returncode == 1
    assert "successor does not exist: PRP-999" in result.stderr


def test_self_referencing_successor_rejected() -> None:
    """Failure: a PRP cannot supersede itself."""
    result = run(case("self_successor"))
    assert result.returncode == 1
    assert "by itself" in result.stderr


def test_unbounded_header_rejected() -> None:
    """Failure: a file with no `---` and no `## ` heading is not PRP-shaped."""
    result = run(case("unbounded"))
    assert result.returncode == 1
    assert "not PRP-shaped" in result.stderr


def test_title_column_comes_from_h1() -> None:
    """Edge: the Title column is the H1 minus its PRP-NNN prefix, not the filename stem."""
    result = run(FIXTURES / "conformant")
    assert result.returncode == 0
    assert "[Draft Case](PRP-001_DRAFT.md)" in result.stdout
    assert "PRP-001:" not in result.stdout


def test_no_traceback_on_nonconformant_corpus() -> None:
    """Failure: a violation is reported, never raised — no traceback reaches the caller."""
    result = run(case("complete"))
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "FAIL" in result.stderr


# ── the silent drops ────────────────────────────────────────────────────────────────────────


def test_misnamed_file_is_violation_not_usage_error() -> None:
    """Failure: a directory of only mis-named files is a populated corpus with violations."""
    result = run(case("misnamed"))
    assert result.returncode == 1, "mis-named alone must be 1, not 2"
    assert "does not match PRP-NNN" in result.stderr


def test_duplicate_number_is_violation() -> None:
    """Failure: two files claiming one number would make the counts header lie."""
    result = run(case("duplicate"))
    assert result.returncode == 1
    assert "duplicate number" in result.stderr


def test_empty_corpus_exits_two_and_writes_nothing() -> None:
    """Failure: an empty match set is a wrong path, and must not overwrite a registry."""
    target = case("empty")
    result = run(target, "--write")
    assert result.returncode == 2
    assert "no PRP markdown" in result.stderr
    assert not (target / "STATUS.md").exists()


def test_missing_directory_exits_two_with_our_message() -> None:
    """Failure: a nonexistent path is a usage error, reported by us and not by python."""
    result = run(Path("/nonexistent-prp-dir"))
    assert result.returncode == 2
    assert "FAIL" in result.stderr, "must be our message, not python's 'can't open file'"


# ── the corpus hazards ──────────────────────────────────────────────────────────────────────


def test_wrapped_status_is_joined_whole() -> None:
    """Edge: a status wrapping onto a second line parses as one value."""
    result = run(FIXTURES / "hazards")
    assert result.returncode == 0
    assert "Do not implement directly" in result.stdout


def test_second_status_deep_in_body_is_ignored() -> None:
    """Edge: only the header block's first Status counts."""
    result = run(FIXTURES / "hazards")
    assert result.returncode == 0
    assert "| 031 | [Second Status](PRP-031_SECOND.md) | \U0001f4cb Draft |" in result.stdout


# ── write safety ────────────────────────────────────────────────────────────────────────────


def test_write_emits_banner_and_is_rerunnable(tmp_path: Path) -> None:
    """Expected: --write produces a bannered file that a second run may overwrite."""
    shutil.copytree(FIXTURES / "conformant", tmp_path / "PRPs")
    assert run(tmp_path / "PRPs", "--write").returncode == 0
    assert (tmp_path / "PRPs" / "STATUS.md").read_text().startswith("<!-- generated by")
    assert run(tmp_path / "PRPs", "--write").returncode == 0


def test_write_refuses_unbannered_status_md(tmp_path: Path) -> None:
    """Failure: a hand-authored registry is never clobbered; the banner is the consent token."""
    shutil.copytree(FIXTURES / "conformant", tmp_path / "PRPs")
    hand = tmp_path / "PRPs" / "STATUS.md"
    hand.write_text("# Hand-written registry\n\nsomething a human wrote\n")
    result = run(tmp_path / "PRPs", "--write")
    assert result.returncode == 2
    assert "without the generated banner" in result.stderr
    assert hand.read_text().startswith("# Hand-written registry")


def test_write_leaves_no_temp_file(tmp_path: Path) -> None:
    """Edge: the write is atomic, so no partial file survives it."""
    shutil.copytree(FIXTURES / "conformant", tmp_path / "PRPs")
    run(tmp_path / "PRPs", "--write")
    assert not list((tmp_path / "PRPs").glob("*.tmp"))


def test_violations_still_render_rows(tmp_path: Path) -> None:
    """Edge: a broken PRP appears as INVALID rather than vanishing from the registry."""
    shutil.copytree(case("complete"), tmp_path / "PRPs")
    result = run(tmp_path / "PRPs")
    assert result.returncode == 1
    assert "INVALID" in result.stdout


# ── the in-flight badge ─────────────────────────────────────────────────────────────────────


def git_repo(tmp_path: Path, branch: str | None) -> Path:
    """Build a throwaway git repo holding the badge fixture, optionally on a named branch."""
    root = tmp_path / "repo"
    prps = root / "PRPs"
    prps.mkdir(parents=True)
    shutil.copy(FIXTURES / "git" / "PRP-040_BADGE.md", prps)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=root,
        check=True,
    )
    if branch:
        subprocess.run(["git", "branch", branch], cwd=root, check=True)
    return prps


def test_in_flight_matches_backtick_wrapped_branch(tmp_path: Path) -> None:
    """Edge: the stored branch is backtick-wrapped, so an unstripped value never matches a ref."""
    prps = git_repo(tmp_path, "feature/prp-040-badge")
    result = run(prps)
    assert result.returncode == 0
    assert "in flight" in result.stdout


def test_no_badge_when_branch_absent(tmp_path: Path) -> None:
    """Failure: a Ready PRP whose branch does not exist is not in flight."""
    prps = git_repo(tmp_path, None)
    result = run(prps)
    assert result.returncode == 0
    assert "in flight" not in result.stdout


def test_in_flight_badge_shown_for_remote_only_branch(tmp_path: Path) -> None:
    """Edge: a fresh clone has no local feature branch, so remote refs must count."""
    prps = git_repo(tmp_path, None)
    ref = "refs/remotes/origin/feature/prp-040-badge"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=prps.parent, capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "update-ref", ref, head], cwd=prps.parent, check=True)
    result = run(prps)
    assert result.returncode == 0
    assert "in flight" in result.stdout


def test_in_flight_without_git_warns_and_exit_unmoved(tmp_path: Path) -> None:
    """Failure: git absent suppresses the badge and warns; the verdict is unaffected."""
    prps = tmp_path / "PRPs"
    prps.mkdir()
    shutil.copy(FIXTURES / "git" / "PRP-040_BADGE.md", prps)
    result = run(prps)
    assert result.returncode == 0, "a badge that cannot be derived must not move the exit code"
    assert "in flight" not in result.stdout
