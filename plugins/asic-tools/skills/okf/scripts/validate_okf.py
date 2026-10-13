#!/usr/bin/env python3
"""Validate an Open Knowledge Format (OKF) v0.1 bundle for conformance.

Conformance (spec §9) — a bundle is conformant if:
  1. Every non-reserved ``.md`` file contains a parseable YAML frontmatter block.
  2. Every frontmatter block contains a non-empty ``type`` field.
  3. Every reserved filename (``index.md``, ``log.md``) follows §6 / §7 when present.

Consumers MUST NOT reject a bundle for missing optional frontmatter fields, unknown ``type``
values, unknown additional keys, broken cross-links, or a missing ``index.md`` (§9). This
validator honours that: none of those ever fail the run.

Exit codes:
    0: conformant (warnings may have been written to stderr)
    1: non-conformant (violations written to stderr)
    2: usage or I/O error
    3: indeterminate — frontmatter outside the parseable subset (a validator limitation, not a
       verdict; a CI gate should treat this as pass-with-warning, never as non-conformant)
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RESERVED: frozenset[str] = frozenset({"index.md", "log.md"})
RECOMMENDED: tuple[str, ...] = ("title", "description", "resource", "tags", "timestamp")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# The OKF frontmatter subset: `key: value` scalars and `key: [a, b]` inline lists (spec §4.1).
KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)[ \t]*:[ \t]*(?P<value>.*)$")
# YAML scalars that denote empty/null once surrounding quotes are stripped. `type` equal to any of
# these is an EMPTY type (§9.2), not truthy content — the single most dangerous false-accept.
YAML_NULLS: frozenset[str] = frozenset({"", "null", "~"})

logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("okf")


class FrontmatterError(ValueError):
    """Raised when a frontmatter block is malformed (e.g. an unclosed `---`) — a §9.1 violation."""


class SubsetError(ValueError):
    """Raised when a frontmatter line is valid YAML but outside the parseable subset.

    A validator limitation, not a bundle defect: it drives exit code 3 (indeterminate), never
    exit 1 (non-conformant). Conflating the two would falsely brand a spec-conformant bundle
    (idiomatic block-sequence or nested-map frontmatter) NON-CONFORMANT.
    """


@dataclass
class Report:
    """Accumulated findings for one bundle."""

    violations: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    concepts: int = 0
    indexes: int = 0
    logs: int = 0


def _strip_quotes(value: str) -> str:
    """Strip one layer of matching surrounding quotes from a scalar value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split a leading frontmatter block from the document body.

    Args:
        text: Full UTF-8 document text.

    Returns:
        A ``(block, body)`` pair, or None when the document has no frontmatter.

    Raises:
        FrontmatterError: If a block opens with ``---`` but never closes.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :])
    raise FrontmatterError("frontmatter opened with '---' but was never closed")


def parse_frontmatter(block: str) -> dict[str, str]:
    """Parse the OKF frontmatter subset into a flat mapping.

    Args:
        block: The text between the opening and closing ``---`` delimiters.

    Returns:
        Mapping of frontmatter key to raw string value, surrounding quotes stripped.

    Raises:
        SubsetError: On any valid-YAML line outside the supported subset (drives exit 3).

    Reason: PyYAML is not importable in this runtime (skill scripts run under bare `python3`),
    so this is a conservative subset parser. It FAILS LOUDLY rather than skipping an
    uninterpretable line — a silently-skipped line could hide a missing `type` and turn a
    non-conformant bundle into a false pass, which is the one failure §9's permissive model
    makes invisible. Out-of-subset lines raise SubsetError (exit 3, a validator limitation), not
    a non-conformance verdict.
    """
    data: dict[str, str] = {}
    for offset, raw in enumerate(block.splitlines()):
        lineno = offset + 2  # +1 for the opening `---`, +1 for 1-based numbering
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = KEY_LINE.match(line)
        if match is None:
            raise SubsetError(
                f"line {lineno}: cannot parse {line!r}. The OKF frontmatter subset supports "
                "`key: value` and `key: [a, b]`. This is valid YAML outside that subset — a "
                "validator limitation, reported (exit 3) rather than passed unchecked or branded "
                "non-conformant."
            )
        # Strip one layer of matching surrounding quotes so `type: ""` / `type: ''` read as EMPTY,
        # not as a two-character truthy string — the §9.2 false-accept on the most important check.
        data[match.group("key")] = _strip_quotes(match.group("value").strip())
    return data


def _has_nonempty_type(block: str) -> bool:
    """Return True iff the block carries an affirmatively parseable, non-empty ``type`` scalar.

    Args:
        block: The text between the opening and closing ``---`` delimiters.

    Returns:
        True when a ``type: <value>`` line is present with a non-null, non-empty scalar value.

    Reason: adjudicates §9.2 independently of the lines the subset parser cannot read, so a
    required ``type`` is confirmed even when an optional field (e.g. a block-sequence ``tags:``)
    makes parse_frontmatter abort before reaching it. A conformant bundle's ``type`` is always a
    plain scalar, so this scan never false-rejects one.
    """
    for raw in block.splitlines():
        match = KEY_LINE.match(raw.rstrip())
        if match is None or match.group("key") != "type":
            continue
        return _strip_quotes(match.group("value").strip()).lower() not in YAML_NULLS
    return False


def check_concept(rel: str, text: str, report: Report) -> None:
    """Apply §9 rules 1 and 2 to a non-reserved concept document."""
    report.concepts += 1
    try:
        split = split_frontmatter(text)
    except FrontmatterError as exc:
        report.violations.append(f"{rel}: {exc}")
        return
    if split is None:
        report.violations.append(f"{rel}: no frontmatter block (§9.1)")
        return
    try:
        data = parse_frontmatter(split[0])
    except SubsetError as exc:
        # Reason: an out-of-subset line is a validator limitation (exit 3) ONLY WHEN the required
        # `type` is still affirmatively present and non-empty. parse_frontmatter aborts on the
        # first line it cannot read, so it may never reach — or may hide the absence of — a `type`
        # that sits below an idiomatic block sequence (`tags:` then `  - urgent`). Recording that
        # as a bare exit-3 limitation would let a MISSING `type` ride through as CI pass-with-
        # warning — the §9.2 false-accept this validator exists to prevent. So re-scan for `type`
        # independently: present-and-non-empty -> limitation (exit 3); absent/empty -> violation
        # (exit 1). A conformant bundle's `type` is a plain scalar, so this never false-rejects one.
        if _has_nonempty_type(split[0]):
            report.limitations.append(f"{rel}: {exc}")
        else:
            report.violations.append(
                f"{rel}: frontmatter has no non-empty `type` (§9.2); a line outside the parseable "
                f"subset cannot mask a missing required field — {exc}"
            )
        return
    # Reason: quotes are already stripped in parse_frontmatter, so `type: ""`, `type: ''`,
    # `type: null`, and `type: ~` all normalise into YAML_NULLS and are rejected as empty (§9.2) —
    # not accepted as truthy content, which would be a silent false-accept on §9's key check.
    if data.get("type", "").strip().lower() in YAML_NULLS:
        report.violations.append(f"{rel}: frontmatter has no non-empty `type` (§9.2)")
        return
    # Reason: §9 forbids consumers rejecting on absent optional fields — warn only.
    for key in RECOMMENDED:
        if key not in data:
            report.warnings.append(f"{rel}: no `{key}` (recommended, §4.1)")


def check_index(rel: str, text: str, is_root: bool, report: Report) -> None:
    """Apply §6 to an ``index.md``, honouring the §11 bundle-root carve-out."""
    report.indexes += 1
    try:
        split = split_frontmatter(text)
    except FrontmatterError as exc:
        report.violations.append(f"{rel}: {exc}")
        return
    if split is not None and not is_root:
        report.violations.append(
            f"{rel}: index.md must contain no frontmatter (§6); only the bundle-root index.md "
            "may carry one, for `okf_version` (§11)"
        )


def check_log(rel: str, text: str, report: Report) -> None:
    """Apply §7: every ``## `` heading must be an ISO 8601 ``YYYY-MM-DD`` date."""
    report.logs += 1
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.startswith("## "):
            heading = raw[3:].strip()
            if not ISO_DATE.match(heading):
                report.violations.append(
                    f"{rel}:{lineno}: log date heading {heading!r} is not ISO 8601 YYYY-MM-DD (§7)"
                )


def iter_markdown(root: Path) -> list[tuple[Path, str]]:
    """Return ``(resolved path, bundle-relative posix path)`` for every safe ``.md`` under root.

    Reason: a symlink resolving outside the bundle root is skipped, never read — CWE-23 path
    traversal, the class Snyk flagged in the former `diagram/scripts` (PRP-008; retired by PRP-021).
    """
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.md")):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            logger.warning("SKIP  %s resolves outside the bundle root", path)
            continue
        if not resolved.is_file():
            continue
        found.append((resolved, path.relative_to(root).as_posix()))
    return found


def validate(root: Path) -> Report:
    """Validate every markdown file in the bundle and return the accumulated report."""
    report = Report()
    for path, rel in iter_markdown(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report.violations.append(f"{rel}: cannot read as UTF-8: {exc}")
            continue
        name = path.name
        if name == "index.md":
            check_index(rel, text, is_root=(rel == "index.md"), report=report)
        elif name == "log.md":
            check_log(rel, text, report)
        else:
            check_concept(rel, text, report)
    return report


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description="Validate an OKF v0.1 bundle.")
    parser.add_argument("bundle", help="path to the OKF bundle root directory")
    parser.add_argument("--quiet", action="store_true", help="suppress recommendation warnings")
    args = parser.parse_args(argv)

    try:
        root = Path(args.bundle).resolve(strict=True)
    except OSError as exc:
        logger.error("cannot resolve bundle path: %s", exc)
        return 2
    if not root.is_dir():
        logger.error("not a directory: %s", root)
        return 2

    report = validate(root)
    if not args.quiet:
        for warning in report.warnings:
            logger.warning("WARN  %s", warning)
    for limitation in report.limitations:
        logger.error("LIMIT %s", limitation)
    for violation in report.violations:
        logger.error("FAIL  %s", violation)

    summary = f"{report.concepts} concept(s), {report.indexes} index, {report.logs} log"
    if report.violations:
        logger.error("NOT CONFORMANT — %d violation(s); %s", len(report.violations), summary)
        return 1
    # Reason: exit 3 (indeterminate) only when there is no outright violation — a real §9 breach
    # always wins. Out-of-subset frontmatter is a validator limitation, not NON-CONFORMANT, so a
    # CI gate can treat 3 as pass-with-warning instead of blocking a spec-conformant bundle.
    if report.limitations:
        logger.error(
            "INDETERMINATE — %d line(s) outside the parseable subset; %s",
            len(report.limitations),
            summary,
        )
        return 3
    logger.info("OK    %s — CONFORMANT (OKF v0.1)", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
