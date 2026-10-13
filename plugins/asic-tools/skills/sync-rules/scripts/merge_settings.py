"""Merge asic-tools' bundled settings fragment into a Claude Code settings.json.

Additive and idempotent: dicts merge recursively, lists gain only the fragment items they lack (in
the target's order, new items appended), absent scalars are added. A scalar the target already sets
to a different value is a CONFLICT and is left alone unless ``--prefer-fragment`` is passed. Nothing
the fragment does not mention is touched, and nothing is ever removed.

Dry-run by default: prints a STATUS line, any conflicts, and a unified diff. ``--write`` applies the
merge atomically and keeps the previous file at ``<target>.sync-rules.bak``.

Exit codes::

    0  success (dry-run or write) -- read the STATUS line: current | pending | conflict
    2  usage or input error -- unreadable or invalid JSON, a top level that is not an object
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# Reason: `attribution: false` hides ALL attribution (v2.1.281+), which is strictly stronger than
# the fragment's per-part object -- treat it as satisfying the fragment, not as a type conflict.
SATISFIED_BY_FALSE = {("attribution",)}


def merge(
    target: Any,
    fragment: Any,
    path: tuple[str, ...],
    conflicts: list[str],
    prefer_fragment: bool,
) -> Any:
    """Return ``target`` with ``fragment`` merged in; record conflicts by dotted path.

    Args:
        target: Current value at this path (may be a dict, list, or scalar).
        fragment: Fragment value at this path.
        path: Key path from the settings root, for conflict messages.
        conflicts: Accumulator for human-readable conflict descriptions.
        prefer_fragment: Take the fragment's value on a scalar or type conflict.

    Returns:
        The merged value. ``target`` is never mutated.
    """
    if target is False and path in SATISFIED_BY_FALSE:
        return target
    if isinstance(target, dict) and isinstance(fragment, dict):
        out = dict(target)
        for key, value in fragment.items():
            if key in out:
                out[key] = merge(out[key], value, (*path, key), conflicts, prefer_fragment)
            else:
                out[key] = value
        return out
    if isinstance(target, list) and isinstance(fragment, list):
        if "$defaults" in fragment and "$defaults" not in target:
            # Reason: a list without "$defaults" deliberately replaced the built-in rules; adding
            # "$defaults" silently would re-enable rules the user chose to own.
            conflicts.append(f'{".".join(path)}: target list omits "$defaults"')
            return _take(target, fragment, prefer_fragment, union=True)
        return target + [item for item in fragment if item not in target]
    if target == fragment:
        return target
    conflicts.append(f"{'.'.join(path)}: target {json.dumps(target)} != {json.dumps(fragment)}")
    return _take(target, fragment, prefer_fragment)


def _take(target: Any, fragment: Any, prefer_fragment: bool, union: bool = False) -> Any:
    """Resolve one conflict: keep the target unless the fragment is preferred."""
    if not prefer_fragment:
        return target
    if union:
        return fragment + [item for item in target if item not in fragment]
    return fragment


def load_object(path: Path) -> dict[str, Any]:
    """Read a JSON object from ``path``; an absent file reads as ``{}``.

    Raises:
        ValueError: If the file is not valid JSON.
        TypeError: If its top level is not an object.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise TypeError(f"{path}: top level is not a JSON object")
    return data


def render(data: dict[str, Any]) -> str:
    """Serialise settings the way Claude Code writes them: 2-space indent, trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` atomically, keeping the old file as a backup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".sync-rules.bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. See the module docstring for the exit-code contract."""
    parser = argparse.ArgumentParser(description="Merge the asic-tools settings fragment.")
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--write", action="store_true", help="apply the merge (default: dry-run)")
    parser.add_argument(
        "--prefer-fragment", action="store_true", help="resolve conflicts to the fragment value"
    )
    args = parser.parse_args(argv)
    try:
        if not args.fragment.is_file():
            raise ValueError(f"{args.fragment}: fragment not found")
        fragment = load_object(args.fragment)
        current = load_object(args.target)
    except (OSError, ValueError, TypeError) as exc:  # JSONDecodeError is a ValueError
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    conflicts: list[str] = []
    merged = merge(current, fragment, (), conflicts, args.prefer_fragment)
    before, after = render(current), render(merged)
    status = (
        "conflict"
        if conflicts and not args.prefer_fragment
        else ("current" if before == after else "pending")
    )
    print(f"STATUS: {status}")
    for line in conflicts:
        print(f"CONFLICT: {line}")
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{args.target} (current)",
        tofile=f"{args.target} (merged)",
    )
    sys.stdout.writelines(diff)
    if args.write and before != after:
        write_atomic(args.target, after)
        print(f"WROTE: {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
