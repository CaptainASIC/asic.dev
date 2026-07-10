#!/usr/bin/env python3
"""Generate a spec-shaped OKF ``index.md`` for one directory of a bundle.

The output follows spec §6: heading-grouped sections of
``* [Title](relative-url) - description`` entries, and **no frontmatter**. Descriptions come from
each concept's frontmatter ``description`` when present (§6: "Entries SHOULD include the
description from the linked concept's frontmatter").

Prints to stdout by default; ``--write`` writes ``index.md`` into the directory.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Reason: reuse the validator's parser so the generator and the checker agree on the subset.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_okf import (  # noqa: E402
    RESERVED,
    FrontmatterError,
    SubsetError,
    parse_frontmatter,
    split_frontmatter,
)

logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("okf-index")


def describe(path: Path) -> tuple[str, str]:
    """Return ``(title, description)`` for a concept, falling back to the filename stem.

    Args:
        path: Path to a concept markdown document.

    Returns:
        Title and description; either may be an empty string when absent or unparseable.
    """
    try:
        text = path.read_text(encoding="utf-8")
        split = split_frontmatter(text)
        data = parse_frontmatter(split[0]) if split else {}
    except (OSError, UnicodeDecodeError, FrontmatterError, SubsetError) as exc:
        logger.warning("WARN  %s: %s — using filename", path.name, exc)
        data = {}
    return data.get("title") or path.stem, data.get("description", "")


def render(directory: Path) -> str:
    """Render the §6 index body for one directory."""
    lines: list[str] = ["# Contents", ""]
    for child in sorted(p for p in directory.iterdir() if p.is_dir()):
        lines.append(f"* [{child.name}]({child.name}/) - ")
    for concept in sorted(directory.glob("*.md")):
        if concept.name in RESERVED:
            continue
        title, description = describe(concept)
        suffix = f" - {description}" if description else " - "
        lines.append(f"* [{title}]({concept.name}){suffix}")
    lines.append("")
    return "\n".join(lines)


def _preserve_frontmatter(target: Path, body: str) -> str:
    """Re-attach any frontmatter block already present in ``target`` above the regenerated body.

    Args:
        target: The ``index.md`` about to be overwritten.
        body: The freshly rendered, frontmatter-free §6 body.

    Returns:
        ``body`` unchanged, or ``body`` with the existing frontmatter block restored on top.

    Reason: render() emits no frontmatter, so overwriting an existing index.md would silently
    destroy a bundle-root ``okf_version`` declaration (§11) — the one place frontmatter is legal
    in an index, and a loss the validator cannot surface (a frontmatter-free root index still
    passes, exit 0). Preserving the existing block keeps regeneration non-destructive; the
    validator still adjudicates whether that frontmatter is legal where it sits.
    """
    if not target.exists():
        return body
    try:
        split = split_frontmatter(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FrontmatterError):
        return body
    if split is None:
        return body
    return f"---\n{split[0]}\n---\n\n{body}"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description="Generate an OKF §6 index.md for a directory.")
    parser.add_argument("directory", help="directory within an OKF bundle")
    parser.add_argument("--write", action="store_true", help="write index.md into the directory")
    args = parser.parse_args(argv)

    try:
        directory = Path(args.directory).resolve(strict=True)
    except OSError as exc:
        logger.error("cannot resolve directory: %s", exc)
        return 2
    if not directory.is_dir():
        logger.error("not a directory: %s", directory)
        return 2

    body = render(directory)
    if args.write:
        target = directory / "index.md"
        # Reason: preserve any existing frontmatter so regenerating a bundle-root index.md does
        # not silently destroy its `okf_version` declaration (§11) — render() emits none.
        body = _preserve_frontmatter(target, body)
        target.write_text(body, encoding="utf-8")
        logger.info("wrote %s", target)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
