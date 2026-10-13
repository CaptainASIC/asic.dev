#!/usr/bin/env python3
"""Keep tool-owned sections of a deployed CLAUDE.md intact across a sync-rules run.

graphify >= 0.9 registers its skill in ``~/.claude/CLAUDE.md`` as a section whose heading line is
exactly ``# graphify`` and refreshes it in place on every ``graphify install``. That section is
graphify's, not the bundled rules'. This helper lets sync-rules compare and write the bundled
rules without diffing such a section away or overwriting it.

Usage:
    owned_blocks.py compose <bundled-source> <deployed-target>
        Print the text sync-rules writes: the bundled source, then every owned block found in the
        target, appended at EOF exactly as graphify appends its own. A missing target composes
        to the source unchanged.

Exit codes:
    0: composed text printed to stdout
    2: usage or I/O error
"""

from __future__ import annotations

import sys
from pathlib import Path

# Heading lines of sections another tool writes into ~/.claude/CLAUDE.md and owns.
OWNED_MARKERS: tuple[str, ...] = ("# graphify",)


def owned_blocks(text: str) -> list[str]:
    """Return every owned block in ``text``, in file order.

    Args:
        text: Full text of a deployed rules file.

    Returns:
        Each block from its marker line to the line before the next line starting with ``#``, or
        EOF, with surrounding blank lines stripped.

    Reason: the boundary is narrower than graphify's own (next H1 or EOF) on purpose. A legacy
    mid-file block followed by an H2 such as ``## Self-test`` must not drag that H2 along.
    """
    lines = text.split("\n")
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() not in OWNED_MARKERS:
            i += 1
            continue
        end = i + 1
        while end < len(lines) and not lines[end].startswith("#"):
            end += 1
        blocks.append("\n".join(lines[i:end]).strip())
        i = end
    return blocks


def compose(source: str, target: str) -> str:
    """Return the bundled source with the target's owned blocks appended at EOF.

    Args:
        source: The bundled rules text.
        target: The deployed text, or ``""`` when the file is absent.

    Returns:
        The exact text sync-rules compares against and writes.

    Reason: the join mirrors graphify's append (``content.rstrip() + "\\n\\n" + section``), so a
    later ``graphify install`` finds its section last, replaces it with identical text, and
    reports "already registered (no change)".
    """
    out = source.rstrip() + "\n"
    for block in owned_blocks(target):
        out += "\n" + block + "\n"
    return out


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] != "compose":
        print("usage: owned_blocks.py compose <bundled-source> <deployed-target>", file=sys.stderr)
        return 2
    try:
        source = Path(args[1]).read_text(encoding="utf-8")
        target_path = Path(args[2])
        target = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(compose(source, target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
