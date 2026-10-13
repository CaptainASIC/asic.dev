#!/usr/bin/env python3
"""Validate an Open Knowledge Format (OKF) v0.2 bundle for conformance.

Conformance (spec §11) — a bundle is conformant if:
  1. Every non-reserved ``.md`` file contains a parseable YAML frontmatter block.
  2. Every frontmatter block contains a non-empty ``type`` field.
  3. Every reserved filename (``index.md``, ``log.md``) follows §8 / §9 when present.

v0.1 bundles are read under §13's fallbacks; superseded v0.1 fields draw warnings, never
failures.

Consumers MUST NOT reject a bundle for missing optional frontmatter fields, unknown ``type``
values, unknown additional keys, broken cross-links, or a missing ``index.md`` (§11). This
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
RECOMMENDED: tuple[str, ...] = ("title", "description", "resource", "tags")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# The OKF frontmatter subset: column-0 `key: value` lines; values may continue on indented lines
# (spec §4.1, §5).
KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)[ \t]*:[ \t]*(?P<value>.*)$")
# YAML scalars that denote empty/null once surrounding quotes are stripped. `type` equal to any of
# these is an EMPTY type (§11 rule 2), not truthy content — the single most dangerous false-accept.
YAML_NULLS: frozenset[str] = frozenset({"", "null", "~"})
# v0.2 §5.4 lifecycle values; an absent `status` means `stable`.
STATUS_VALUES: frozenset[str] = frozenset({"draft", "stable", "deprecated"})
# v0.2 §5: every timestamp-valued key is an ISO 8601 datetime with an explicit UTC offset.
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$")
# YAML opens a comment with `#` only at value start or after whitespace (`C#`, `x#frag` survive).
INLINE_COMMENT = re.compile(r"(^|\s)#.*$")
# Block-scalar indicators (`|`, `>`, optional chomping/indent): the text is on indented lines.
BLOCK_SCALAR = re.compile(r"^[|>]([+-]?[1-9]?|[1-9][+-])$")

logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("okf")


class FrontmatterError(ValueError):
    """Raised when a frontmatter block is malformed (e.g. an unclosed `---`) — a §11 rule 1 violation."""


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


def _scalar(value: str) -> str:
    """Normalise a raw scalar: unquote it, or strip a trailing YAML comment when unquoted.

    Args:
        value: The text after ``key:`` on a frontmatter line.

    Returns:
        The scalar's content; ``""`` for an empty or comment-only value.

    Reason: ``type: ""``, ``type: null``, ``type: ~`` and ``type: # todo`` are all an EMPTY type
    (§11 rule 2) — the comment-only form was a silent false-accept before v0.2 support. v0.2's own
    examples also put comments after values (§5.4 ``status: stable  # draft | …``), which the soft
    checks must not misread.
    """
    value = value.strip()
    if value[:1] in ('"', "'"):
        end = value.find(value[0], 1)
        return value[1:end].strip() if end != -1 else value
    return INLINE_COMMENT.sub("", value).strip()


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
    """Parse the top level of an OKF frontmatter block into a flat mapping.

    Args:
        block: The text between the opening and closing ``---`` delimiters.

    Returns:
        Each column-0 key mapped to its normalised inline value. A key whose value is a block —
        indented lines, or ``- `` items under an empty inline value — maps to its inline text:
        ``""`` for a block sequence or nested map, the indicator for a block scalar.

    Raises:
        SubsetError: On a line that is neither a column-0 ``key: value`` nor part of the preceding
            key's block (drives exit 3).

    Reason: v0.2 nests idiomatically — ``sources:`` (§5.1), ``verified:`` (§5.2), ``executor:`` /
    ``attester:`` (§10.2) — so an indented or block-opened line is the preceding key's value and is
    consumed as such, never skipped unexamined. Only column-0 lines introduce keys, which keeps a
    nested ``  type:`` from ever satisfying the required top-level ``type``. Anything else still
    raises SubsetError: a validator limitation (exit 3), never a non-conformance verdict. PyYAML
    is not importable here (bare ``python3``), so this stays a conservative structural parser.
    """
    data: dict[str, str] = {}
    current: str | None = None
    block_open = False
    for offset, raw in enumerate(block.splitlines()):
        lineno = offset + 2  # +1 for the opening `---`, +1 for 1-based numbering
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("\t"):
            raise SubsetError(
                f"line {lineno}: tab-indented {line!r}. YAML forbids tabs for indentation — "
                "reported (exit 3) rather than guessed at."
            )
        if line.startswith(" ") or (block_open and (line == "-" or line.startswith("- "))):
            if current is None:
                raise SubsetError(
                    f"line {lineno}: indented {line!r} before any key — reported (exit 3) "
                    "rather than passed unchecked."
                )
            continue  # Reason: part of `current`'s block value — consumed, never a key.
        match = KEY_LINE.match(line)
        if match is None:
            raise SubsetError(
                f"line {lineno}: cannot parse {line!r}. The OKF frontmatter subset supports "
                "column-0 `key: value` lines whose values may continue on indented lines. This is "
                "valid YAML outside that subset — a validator limitation, reported (exit 3) rather "
                "than passed unchecked or branded non-conformant."
            )
        current = match.group("key")
        data[current] = _scalar(match.group("value"))
        block_open = data[current] == ""
    return data


def _has_nonempty_type(block: str) -> bool:
    """Return True iff the block carries an affirmatively parseable, non-empty ``type`` scalar.

    Args:
        block: The text between the opening and closing ``---`` delimiters.

    Returns:
        True when a ``type: <value>`` line is present with a non-null, non-empty scalar value.

    Reason: adjudicates §11 rule 2 independently of the lines the subset parser cannot read, so a
    required ``type`` is confirmed even when an optional field (e.g. a block-sequence ``tags:``)
    makes parse_frontmatter abort before reaching it. A conformant bundle's ``type`` is always a
    plain scalar, so this scan never false-rejects one. A block-scalar indicator with no
    indented content line is empty.
    """
    lines = block.splitlines()
    for index, raw in enumerate(lines):
        match = KEY_LINE.match(raw.rstrip())
        if match is None or match.group("key") != "type":
            continue
        value = _scalar(match.group("value"))
        if BLOCK_SCALAR.match(value):
            # Reason: `type: |` / `>` / `>-` is only an indicator; YAML's value is the indented
            # text below it, and with none it is "" — an EMPTY type (§11 rule 2), the same
            # false-accept class as `type: # todo`. Non-empty only if the next non-blank line
            # is an indented content line.
            following = [ln for ln in lines[index + 1 :] if ln.strip()]
            return bool(following) and following[0].startswith(" ")
        return value.lower() not in YAML_NULLS
    return False


def _soft_checks(rel: str, data: dict[str, str], body: str, report: Report) -> None:
    """Warn, never fail, on v0.1 holdovers (§13.1) and malformed v0.2 lifecycle values (§5).

    Reason: §11 makes everything beyond its three rules soft guidance and forbids rejecting a
    concept for a missing optional family — these are migration hints, not verdicts.
    """
    if "timestamp" in data and "generated" not in data:
        report.warnings.append(
            f"{rel}: legacy v0.1 `timestamp`; v0.2 records this as `generated: {{by, at}}` (§13.1)"
        )
    if "sources" not in data and any(ln.strip() == "# Citations" for ln in body.splitlines()):
        report.warnings.append(
            f"{rel}: legacy v0.1 `# Citations` body list; v0.2 moves provenance to "
            "frontmatter `sources` (§13.1)"
        )
    status = data.get("status", "")
    if status and status not in STATUS_VALUES:
        report.warnings.append(f"{rel}: `status: {status}` is not draft|stable|deprecated (§5.4)")
    stale = data.get("stale_after", "")
    if stale and not ISO_DATETIME.match(stale):
        report.warnings.append(
            f"{rel}: `stale_after: {stale}` is not an ISO 8601 datetime with an explicit "
            "offset (§5.5)"
        )


def check_concept(rel: str, text: str, report: Report) -> None:
    """Apply §11 rules 1 and 2 to a non-reserved concept document."""
    report.concepts += 1
    try:
        split = split_frontmatter(text)
    except FrontmatterError as exc:
        report.violations.append(f"{rel}: {exc}")
        return
    if split is None:
        report.violations.append(f"{rel}: no frontmatter block (§11 rule 1)")
        return
    try:
        data = parse_frontmatter(split[0])
    except SubsetError as exc:
        # Reason: an out-of-subset line is a validator limitation (exit 3) ONLY WHEN the required
        # `type` is still affirmatively present and non-empty. parse_frontmatter aborts on the
        # first line it cannot read, so it may never reach — or may hide the absence of — a `type`
        # that sits below an idiomatic block sequence (`tags:` then `  - urgent`). Recording that
        # as a bare exit-3 limitation would let a MISSING `type` ride through as CI pass-with-
        # warning — the §11 rule 2 false-accept this validator exists to prevent. So re-scan for `type`
        # independently: present-and-non-empty -> limitation (exit 3); absent/empty -> violation
        # (exit 1). A conformant bundle's `type` is a plain scalar, so this never false-rejects one.
        if _has_nonempty_type(split[0]):
            report.limitations.append(f"{rel}: {exc}")
        else:
            report.violations.append(
                f"{rel}: frontmatter has no non-empty `type` (§11 rule 2); a line outside the parseable "
                f"subset cannot mask a missing required field — {exc}"
            )
        return
    # Reason: one judgement for both paths — `type: ""`, `type: ''`, `type: null`, `type: ~`,
    # `type: # todo` and a block-scalar `type: |` with no indented content are all EMPTY (§11 rule
    # 2); parse_frontmatter records the bare indicator for a block scalar, which a plain null test
    # would accept as truthy content.
    if not _has_nonempty_type(split[0]):
        report.violations.append(f"{rel}: frontmatter has no non-empty `type` (§11 rule 2)")
        return
    # Reason: §11 forbids consumers rejecting on absent optional fields — warn only.
    for key in RECOMMENDED:
        if key not in data:
            report.warnings.append(f"{rel}: no `{key}` (recommended, §4.1)")
    _soft_checks(rel, data, split[1], report)


def check_index(rel: str, text: str, is_root: bool, report: Report) -> None:
    """Apply §8 to an ``index.md``, honouring the §12 bundle-root carve-out."""
    report.indexes += 1
    try:
        split = split_frontmatter(text)
    except FrontmatterError as exc:
        report.violations.append(f"{rel}: {exc}")
        return
    if split is not None and not is_root:
        report.violations.append(
            f"{rel}: index.md must contain no frontmatter (§8); only the bundle-root index.md "
            "may carry one, for `okf_version` (§12)"
        )


def check_log(rel: str, text: str, report: Report) -> None:
    """Apply §9: every ``## `` heading must be an ISO 8601 ``YYYY-MM-DD`` date."""
    report.logs += 1
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if raw.startswith("## "):
            heading = raw[3:].strip()
            if not ISO_DATE.match(heading):
                report.violations.append(
                    f"{rel}:{lineno}: log date heading {heading!r} is not ISO 8601 YYYY-MM-DD (§9)"
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
    parser = argparse.ArgumentParser(
        description="Validate an OKF v0.2 bundle (v0.1 read under §13 fallbacks)."
    )
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
    # Reason: exit 3 (indeterminate) only when there is no outright violation — a real §11 breach
    # always wins. Out-of-subset frontmatter is a validator limitation, not NON-CONFORMANT, so a
    # CI gate can treat 3 as pass-with-warning instead of blocking a spec-conformant bundle.
    if report.limitations:
        logger.error(
            "INDETERMINATE — %d line(s) outside the parseable subset; %s",
            len(report.limitations),
            summary,
        )
        return 3
    logger.info("OK    %s — CONFORMANT (OKF v0.2)", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
