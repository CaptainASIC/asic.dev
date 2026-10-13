"""Tests for the OKF conformance validator and index generator.

The scripts are standalone CLI tools invoked as ``python3 <path> <args>`` (the toolbox's
stdlib-script convention), not an importable package, so these tests drive the CLI by subprocess
and assert on returncode and stderr. That tests exactly the contract ``SKILL.md`` tells the agent
to run.

Exit contract: 0 conformant, 1 non-conformant, 2 usage/IO error, 3 indeterminate (frontmatter
outside the parseable subset — a validator limitation, never a non-conformance verdict).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONFORMANT = FIXTURES / "conformant"
BAD = FIXTURES / "nonconformant"


def run_validator(bundle: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Drive the validator CLI exactly as SKILL.md instructs, capturing stderr."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_okf.py"), str(bundle), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def run_index(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Drive the index generator CLI, capturing stdout."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "okf_index.py"), str(directory), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------- expected use


def test_conformant_bundle_exits_zero() -> None:
    """Expected: a conformant bundle validates clean."""
    result = run_validator(CONFORMANT)
    assert result.returncode == 0, result.stderr
    assert "CONFORMANT" in result.stderr


def test_root_index_may_carry_frontmatter() -> None:
    """Expected: the bundle-root index.md may declare okf_version (§11 carve-out)."""
    assert "okf_version" in (CONFORMANT / "index.md").read_text(encoding="utf-8")
    assert run_validator(CONFORMANT).returncode == 0


# ------------------------------------------------- edge: §9's MUST-NOT-reject list (all exit 0)


def test_unknown_type_accepted() -> None:
    """Edge: §9 forbids rejecting an unknown `type` value."""
    assert "Totally Invented Type" in (CONFORMANT / "rich.md").read_text(encoding="utf-8")
    assert run_validator(CONFORMANT).returncode == 0


def test_unknown_extra_keys_accepted() -> None:
    """Edge: §9 forbids rejecting unknown additional frontmatter keys."""
    assert "custom_extension_key" in (CONFORMANT / "rich.md").read_text(encoding="utf-8")
    assert run_validator(CONFORMANT).returncode == 0


def test_broken_cross_link_accepted() -> None:
    """Edge: §5.3/§9 — consumers MUST tolerate broken cross-links."""
    assert "does-not-exist.md" in (CONFORMANT / "rich.md").read_text(encoding="utf-8")
    assert run_validator(CONFORMANT).returncode == 0


def test_missing_index_accepted() -> None:
    """Edge: §9 forbids rejecting a bundle for a missing index.md."""
    assert not (CONFORMANT / "playbooks" / "index.md").exists()
    assert run_validator(CONFORMANT).returncode == 0


def test_missing_recommended_fields_warn_but_pass() -> None:
    """Edge: absent recommended fields warn on stderr but never fail (§9, §3.6)."""
    result = run_validator(CONFORMANT)
    assert result.returncode == 0
    assert "WARN" in result.stderr
    assert "description" in result.stderr


def test_quiet_suppresses_warnings() -> None:
    """Edge: --quiet silences recommendation warnings, still exits 0."""
    result = run_validator(CONFORMANT, "--quiet")
    assert result.returncode == 0
    assert "WARN" not in result.stderr


# --------------------------------------------------------------------------- failure cases


def test_missing_type_rejected() -> None:
    """Failure: frontmatter without `type` violates §9.2."""
    result = run_validator(BAD / "missing_type")
    assert result.returncode == 1
    assert "no non-empty `type`" in result.stderr


def test_empty_type_rejected() -> None:
    """Failure: a bare `type:` with no value is an empty type (§9.2)."""
    result = run_validator(BAD / "empty_type")
    assert result.returncode == 1
    assert "no non-empty `type`" in result.stderr


def test_quoted_empty_type_rejected() -> None:
    """Failure: `type: ""` must not read as truthy two-character content (§9.2 false-accept)."""
    result = run_validator(BAD / "quoted_empty_type")
    assert result.returncode == 1
    assert "no non-empty `type`" in result.stderr


def test_null_type_rejected() -> None:
    """Failure: YAML null sentinels (`null`, `~`) are an empty `type`, not a value (§9.2)."""
    result = run_validator(BAD / "null_type")
    assert result.returncode == 1
    assert "no non-empty `type`" in result.stderr


def test_no_frontmatter_rejected() -> None:
    """Failure: a concept with no frontmatter block violates §9.1."""
    result = run_validator(BAD / "no_frontmatter")
    assert result.returncode == 1
    assert "no frontmatter block" in result.stderr


def test_unclosed_frontmatter_rejected() -> None:
    """Failure: an unclosed `---` block is malformed — no YAML parser accepts it (§9.1)."""
    result = run_validator(BAD / "unclosed_frontmatter")
    assert result.returncode == 1
    assert "never closed" in result.stderr


def test_unparseable_line_rejected_not_skipped() -> None:
    """Failure: an out-of-subset line surfaces loudly as exit 3, never a silent skip (§3.3)."""
    result = run_validator(BAD / "unparseable_line")
    assert result.returncode == 3
    assert "cannot parse" in result.stderr


def test_block_sequence_in_extra_field_is_loud_fail() -> None:
    """Failure: a block sequence in an extra field is a limitation (3), not NON-CONFORMANT (1)."""
    result = run_validator(BAD / "block_seq_extra")
    assert result.returncode == 3
    assert "cannot parse" in result.stderr


def test_missing_type_behind_block_sequence_rejected() -> None:
    """Failure: an out-of-subset line must never mask an absent required `type` (§6.1 blocker)."""
    result = run_validator(BAD / "missing_type_block_seq")
    assert result.returncode == 1, f"exit 3 would wave a missing type through: {result.stderr}"
    assert "no non-empty `type`" in result.stderr


def test_nonroot_index_with_frontmatter_rejected() -> None:
    """Failure: only the bundle-root index.md may carry frontmatter (§6, §11)."""
    result = run_validator(BAD / "index_with_frontmatter")
    assert result.returncode == 1
    assert "no frontmatter" in result.stderr


def test_bad_log_date_rejected() -> None:
    """Failure: a log.md date heading must be ISO 8601 YYYY-MM-DD (§7)."""
    result = run_validator(BAD / "bad_log_date")
    assert result.returncode == 1
    assert "ISO 8601" in result.stderr


def test_missing_bundle_path_exits_two() -> None:
    """Failure: a nonexistent bundle path is a usage error, reported without a traceback.

    Reason: asserts the validator's own message, not just exit 2. A bare `returncode == 2` also
    matches python's "can't open file" when the script is absent, so the check would pass even with
    no validator at all — a test that cannot fail.
    """
    result = run_validator(Path("/nonexistent-okf-bundle"))
    assert result.returncode == 2
    assert "cannot resolve bundle path" in result.stderr
    assert "Traceback" not in result.stderr


def test_bundle_path_is_a_file_exits_two(tmp_path: Path) -> None:
    """Failure: a file where a directory is required is a usage error.

    Reason: asserts the validator's own "not a directory" message for the same reason as above.
    """
    target = tmp_path / "not-a-dir.md"
    target.write_text("---\ntype: Reference\n---\n", encoding="utf-8")
    result = run_validator(target)
    assert result.returncode == 2
    assert "not a directory" in result.stderr


# --------------------------------------------------------------------------- security


def test_symlink_outside_root_is_skipped(tmp_path: Path) -> None:
    """Security: a symlink resolving outside the bundle is skipped, never read (CWE-23)."""
    bundle = tmp_path / "bundle"
    shutil.copytree(CONFORMANT, bundle)
    (bundle / "escape.md").symlink_to("/etc/hosts")
    result = run_validator(bundle)
    assert result.returncode == 0, result.stderr
    assert "SKIP" in result.stderr


def test_index_skips_symlink_outside_dir(tmp_path: Path) -> None:
    """Security: the generator must not read a symlinked entry escaping the directory (CWE-23).

    Reason: `describe()` reads every discovered `.md`. Without a containment guard the generator
    would be the soft spot the validator's `iter_markdown` closes.
    """
    directory = tmp_path / "d"
    directory.mkdir()
    (directory / "real.md").write_text("---\ntype: Reference\n---\n", encoding="utf-8")
    (directory / "escape.md").symlink_to("/etc/hosts")
    result = run_index(directory)
    assert result.returncode == 0, result.stderr
    assert "SKIP" in result.stderr
    assert "escape.md" not in result.stdout
    assert "* [real](real.md)" in result.stdout


# --------------------------------------------------------------------------- generator output shape


def test_index_entry_uses_description() -> None:
    """Expected: a described concept renders as `* [Title](file.md) - <desc>` (§6)."""
    result = run_index(CONFORMANT / "tables")
    assert result.returncode == 0, result.stderr
    assert "* [Customer Orders](orders.md) - One row per completed customer order." in result.stdout


def test_index_title_falls_back_to_stem() -> None:
    """Edge: a concept with no `title` is listed by its filename stem."""
    result = run_index(CONFORMANT)
    assert result.returncode == 0, result.stderr
    assert "* [minimal](minimal.md)" in result.stdout


def test_index_lists_subdirectories() -> None:
    """Expected: child directories are listed as `* [name](name/) -` (§6)."""
    result = run_index(CONFORMANT)
    assert result.returncode == 0, result.stderr
    assert "* [tables](tables/) -" in result.stdout


def test_generated_body_has_no_frontmatter() -> None:
    """Expected: the generated index body carries no frontmatter (§6)."""
    result = run_index(CONFORMANT / "tables")
    assert result.returncode == 0, result.stderr
    assert not any(line.strip() == "---" for line in result.stdout.splitlines())


# --------------------------------------------------------------------------- round-trip


def test_generated_index_is_conformant(tmp_path: Path) -> None:
    """Integration: a generated index.md validates conformant (necessary, not sufficient)."""
    bundle = tmp_path / "bundle"
    shutil.copytree(CONFORMANT, bundle)
    assert run_index(bundle / "tables", "--write").returncode == 0
    assert run_validator(bundle).returncode == 0


def test_write_preserves_root_okf_version(tmp_path: Path) -> None:
    """Integration: --write must not destroy the bundle-root okf_version frontmatter (§11)."""
    bundle = tmp_path / "bundle"
    shutil.copytree(CONFORMANT, bundle)
    assert run_index(bundle, "--write").returncode == 0
    regenerated = (bundle / "index.md").read_text(encoding="utf-8")
    assert "okf_version" in regenerated, "regeneration silently destroyed the §11 declaration"
    assert run_validator(bundle).returncode == 0
