#!/usr/bin/env python3
"""Extract a Rust crate's module-use graph as autolayout graph JSON.

The Rust counterpart to pyimports.py / jsimports.py / goimports.py. Treats each
.rs file as a module (path-derived: src/foo/bar.rs -> module foo::bar; main.rs /
lib.rs / mod.rs name the enclosing module), and records intra-crate `use` edges
resolved through Rust's path roots:

  use crate::a::b::C;   -> edge to module a::b
  use super::sibling;   -> resolved against the current module's parent
  use self::child::Item;-> resolved against the current module
  use other_crate::...; / use std::...;  -> external, ignored

Brace groups (`use crate::a::{B, C};`, `use crate::{a, b};`) are expanded.
Transitive reduction is on by default so the diagram stays readable.

  python3 rustimports.py ./mycrate --group -o graph.json
  python3 autolayout.py graph.json -o diagram.drawio

Parsing is regex-based, not a full parser: inline `mod { ... }` blocks are not
split out, `#[cfg]`-gated modules are always included, and 2015-edition bare
intra-crate paths (without `crate::`) are not resolved.

Usage: python3 rustimports.py <crate_dir> [-o graph.json] [--direction TB|LR]
                                           [--group] [--no-reduce]
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys

logger = logging.getLogger(__name__)

USE: re.Pattern[str] = re.compile(r"\buse\s+([^;]+);")


def crate_name(root: str) -> str:
    """Read the crate name from Cargo.toml at the crate root.

    Args:
        root: Path to the crate directory.

    Returns:
        The declared crate name, or "crate" when Cargo.toml is missing or has
        no name field.
    """
    cargo = os.path.join(root, "Cargo.toml")
    if os.path.exists(cargo):
        with open(cargo, encoding="utf-8", errors="ignore") as fh:
            m = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', fh.read())
        if m:
            return m.group(1)
    return "crate"


def discover(root: str) -> tuple[dict[tuple[str, ...], str], str]:
    """Discover every .rs module under a crate root.

    Args:
        root: Path to the crate directory.

    Returns:
        A tuple of (module path -> file path mapping, source root path). Each
        module path is a tuple of segments; the empty tuple is the crate root.
    """
    root = os.path.abspath(root)
    src = os.path.join(root, "src") if os.path.isdir(os.path.join(root, "src")) else root
    modules: dict[tuple[str, ...], str] = {}
    for dirpath, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "target" and not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".rs"):
                continue
            parts = os.path.relpath(os.path.join(dirpath, fn), src)[:-3].split(os.sep)
            if parts[-1] == "mod":
                parts = parts[:-1]
            if len(parts) == 1 and parts[0] in ("main", "lib"):
                parts = []  # crate root
            modules[tuple(parts)] = os.path.join(dirpath, fn)
    return modules, src


def split_top(inner: str) -> list[str]:
    """Split a brace group on top-level commas, ignoring nested braces.

    Args:
        inner: The content between the outermost braces of a `use` group.

    Returns:
        The list of top-level comma-separated segments.
    """
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in inner:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def base_segments(prefix: str, current: tuple[str, ...]) -> list[str] | None:
    """Classify a `use` path prefix into intra-crate base segments.

    Args:
        prefix: The path prefix before any brace group.
        current: The current module path (tuple of segments).

    Returns:
        The resolved base segments for an intra-crate path, or None when the
        path is external (std / another crate) or climbs above the crate root.
    """
    segs = [s for s in (p.strip() for p in prefix.split("::")) if s]
    if not segs:
        return None
    # Reason: Rust path roots -- `crate::` is absolute from the crate root,
    # `self::` is relative to the current module, `super::` climbs one parent
    # per occurrence; anything else (std, another crate name) is external.
    if segs[0] == "crate":
        return segs[1:]
    if segs[0] == "self":
        return list(current) + segs[1:]
    if segs[0] == "super":
        n = 0
        while segs and segs[0] == "super":
            n += 1
            segs = segs[1:]
        if n > len(current):
            return None  # climbs above the crate root
        return list(current)[: len(current) - n] + segs
    return None  # std / external crate


def resolve(
    parts: tuple[str, ...],
    modules: dict[tuple[str, ...], str],
    current: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Find the longest known module prefix of a path.

    Args:
        parts: The candidate module path segments.
        modules: Mapping of known module paths to file paths.
        current: The current module path (excluded from results).

    Returns:
        The longest known module path that prefixes `parts` (and is not the
        current module), or None when no known prefix matches.
    """
    if not parts:
        return () if () in modules and () != tuple(current) else None
    p = list(parts)
    while p:
        if tuple(p) in modules and tuple(p) != tuple(current):
            return tuple(p)
        p = p[:-1]
    return None


def edges_of(
    current: tuple[str, ...],
    path: str,
    modules: dict[tuple[str, ...], str],
) -> set[tuple[str, ...]]:
    """Find the intra-crate module paths used by a module.

    Args:
        current: The current module path (tuple of segments).
        path: Absolute path to the current module's file.
        modules: Mapping of known module paths to file paths.

    Returns:
        The set of intra-crate module paths that `current` uses.
    """
    found: set[tuple[str, ...]] = set()
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            src = fh.read()
    except OSError:
        # Reason: unreadable source file is bad data -- skip and continue.
        return found
    for stmt in USE.findall(src):
        if "{" in stmt:
            prefix = stmt[: stmt.index("{")]
            inner = stmt[stmt.index("{") + 1 : stmt.rindex("}")] if "}" in stmt else ""
            leaves: list[str | None] = list(split_top(inner))
        else:
            prefix, leaves = stmt, [None]
        base = base_segments(prefix, current)
        if base is None:
            continue
        for leaf in leaves:
            segs = list(base)
            if leaf:
                first = leaf.strip().split("::")[0].split()[0]
                if first and first not in ("self", "*"):
                    segs.append(first)
            target = resolve(tuple(segs), modules, current)
            if target is not None and target != current:
                found.add(target)
    return found


def transitive_reduce(
    nodes: list[str],
    edges: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Drop edges implied by a longer path, via Graphviz `tred`.

    Args:
        nodes: Ordered list of node ids (defines the integer index mapping).
        edges: List of (source, target) edges.

    Returns:
        The transitively reduced edge list, or the original edges unchanged
        when `tred` is unavailable or fails.
    """
    # Reason: transitive reduction removes an edge A->C when a longer path
    # A->B->C already implies it, keeping the diagram readable; `tred` does
    # this over a DOT digraph keyed by integer node indices.
    idx = {n: i for i, n in enumerate(nodes)}
    dot = "digraph{" + "".join(f"{idx[s]}->{idx[t]};" for s, t in edges) + "}"
    try:
        out = subprocess.run(
            ["tred"],
            input=dot,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        logger.warning("tred unavailable, keeping all edges (%s)", exc)
        return edges
    rev = {i: n for n, i in idx.items()}
    return [(rev[int(a)], rev[int(b)]) for a, b in re.findall(r"(\d+)\s*->\s*(\d+)", out)]


def main() -> None:
    """Build and emit the Rust module-use graph as autolayout graph JSON.

    Returns:
        None. Writes the JSON graph to stdout or the output file, and logs
        progress to stderr.

    Raises:
        SystemExit: When no .rs modules are found under the crate dir.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(
        description="Rust module-use graph -> autolayout graph JSON.",
    )
    ap.add_argument("crate", help="crate directory (contains Cargo.toml and/or src/)")
    ap.add_argument("-o", "--output", help="output JSON path (default: stdout)")
    ap.add_argument("--direction", default="TB", choices=["TB", "LR"])
    ap.add_argument(
        "--group",
        action="store_true",
        help="box modules by their parent module path (nested)",
    )
    ap.add_argument(
        "--no-reduce",
        action="store_true",
        help="keep every edge (skip transitive reduction)",
    )
    args = ap.parse_args()

    modules, _ = discover(args.crate)
    if not modules:
        sys.exit(f"error: no .rs modules found under {args.crate}")
    name = crate_name(args.crate)

    def mid(parts: tuple[str, ...]) -> str:
        """Render a module path tuple as its id (crate name for the root)."""
        return name if not parts else "::".join(parts)

    edges = sorted(
        {(mid(m), mid(t)) for m, path in modules.items() for t in edges_of(m, path, modules)},
    )
    raw = len(edges)
    if not args.no_reduce:
        edges = transitive_reduce([mid(m) for m in modules], edges)

    def node(parts: tuple[str, ...]) -> dict[str, str]:
        """Build the node dict for a module path, optionally with a group."""
        d = {"id": mid(parts), "label": name if not parts else parts[-1]}
        if args.group and len(parts) > 1:
            d["group"] = "/".join(parts[:-1])  # parent module path -> nested boxes
        return d

    graph = {
        "direction": args.direction,
        "nodes": [node(m) for m in modules],
        "edges": [{"source": s, "target": t} for s, t in edges],
    }
    text = json.dumps(graph, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        logger.info("wrote %s", args.output)
    else:
        sys.stdout.write(text)
    note = "" if args.no_reduce else f" (reduced from {raw})"
    logger.info("%d modules, %d edges%s", len(modules), len(edges), note)


if __name__ == "__main__":
    main()
