#!/usr/bin/env python3
"""Extract a Python project's module-import graph as autolayout graph JSON.

Walks a package/project directory, parses each module with ``ast``, builds the
intra-project import edges, and (by default) applies transitive reduction so
the diagram stays readable instead of becoming a hairball. The output feeds
autolayout.py::

    python3 pyimports.py myproject -o graph.json
    python3 autolayout.py graph.json -o diagram.drawio

Transitive reduction uses Graphviz ``tred`` (drops edges implied by a longer
path); pass ``--no-reduce`` to keep every import edge. Only intra-project
imports are kept -- third-party and stdlib imports are ignored.

Usage:
    python3 pyimports.py <project_dir> [-o graph.json] [--direction TB|LR] [--no-reduce]
"""

import argparse
import ast
import json
import logging
import os
import re
import subprocess
import sys

logger = logging.getLogger(__name__)


def discover(root: str) -> tuple[dict[str, str], str]:
    """Map every ``.py`` module under ``root`` to its file path.

    If ``root`` is itself a package (has ``__init__.py``), module names are
    qualified with its name so the project's own absolute imports resolve.

    Args:
        root: Package or project directory to scan.

    Returns:
        A tuple of (mapping of dotted module name -> file path, package prefix).
    """
    root = os.path.abspath(root)
    base = os.path.basename(root) if os.path.exists(os.path.join(root, "__init__.py")) else ""
    modules: dict[str, str] = {}
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)[:-3]  # strip .py
            parts = rel.split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]  # package = its dir
            parts = ([base] + parts) if base else parts
            if parts:
                modules[".".join(parts)] = os.path.join(dirpath, fn)
    return modules, base


def resolve(name: str, current: str, modules: dict[str, str]) -> str | None:
    """Resolve a dotted name to the longest known module prefix.

    Args:
        name: Dotted name being imported.
        current: Module doing the importing (never resolves to itself).
        modules: Mapping of dotted module name -> file path.

    Returns:
        The matching module name, or ``None`` if no prefix is a known module.
    """
    parts = name.split(".") if name else []
    while parts:
        cand = ".".join(parts)
        if cand in modules and cand != current:
            return cand
        parts = parts[:-1]
    return None


def edges_of(name: str, path: str, modules: dict[str, str]) -> set[str]:
    """Find the intra-project modules imported by ``name``.

    Args:
        name: Dotted name of the importing module.
        path: File path of the importing module.
        modules: Mapping of dotted module name -> file path.

    Returns:
        Set of intra-project module names imported by ``name``.
    """
    pkg = name if path.endswith("__init__.py") else name.rsplit(".", 1)[0] if "." in name else ""
    found: set[str] = set()
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except SyntaxError:
        # Reason: a single unparseable module is bad data -- skip it and keep going.
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):  # import a.b.c
            for alias in node.names:
                target = resolve(alias.name, name, modules)
                if target:
                    found.add(target)
        elif isinstance(node, ast.ImportFrom):  # from a.b import c
            if node.level:
                # Reason: relative import -- climb (level-1) packages up from the
                # importing module's package to form the absolute base.
                base = pkg.split(".") if pkg else []
                base = base[: len(base) - (node.level - 1)]
                prefix = ".".join(base)
                mod = (
                    f"{prefix}.{node.module}" if prefix and node.module else (node.module or prefix)
                )
            else:
                mod = node.module or ""
            target = resolve(mod, name, modules)
            if target:
                found.add(target)
            for alias in node.names:  # `from pkg import submodule`
                sub = f"{mod}.{alias.name}" if mod else alias.name
                target = resolve(sub, name, modules)
                if target:
                    found.add(target)
    return found


def transitive_reduce(
    nodes: list[str],
    edges: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Drop edges implied by a longer path, via Graphviz ``tred``.

    Args:
        nodes: All node names, used to assign stable integer ids.
        edges: List of (source, target) edges to reduce.

    Returns:
        The reduced edge list, or the original ``edges`` if ``tred`` is
        unavailable.
    """
    idx = {n: i for i, n in enumerate(nodes)}
    # Reason: tred reads/writes integer-id DOT; map names <-> ids around the call.
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
    """Parse args, build the import graph, and emit autolayout graph JSON."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Python import graph -> autolayout graph JSON.")
    ap.add_argument("project", help="package or project directory")
    ap.add_argument("-o", "--output", help="output JSON path (default: stdout)")
    ap.add_argument("--direction", default="TB", choices=["TB", "LR"])
    ap.add_argument(
        "--group",
        action="store_true",
        help="group nodes into containers by sub-package",
    )
    ap.add_argument(
        "--no-reduce",
        action="store_true",
        help="keep every edge (skip transitive reduction)",
    )
    args = ap.parse_args()

    modules, base = discover(args.project)
    if not modules:
        sys.exit(f"error: no .py modules found under {args.project}")
    edges = sorted(
        {(name, t) for name, path in modules.items() for t in edges_of(name, path, modules)},
    )
    raw = len(edges)
    if not args.no_reduce:
        edges = transitive_reduce(list(modules), edges)
    # Drop the shared package prefix from labels for readability; ids stay full.
    strip = base + "." if base else ""

    def label(m: str) -> str:
        """Strip the shared package prefix from a module name for display."""
        return m[len(strip) :] if strip and m.startswith(strip) else m

    def node(m: str) -> dict[str, str]:
        """Build the graph node dict for module ``m``."""
        d = {"id": m, "label": label(m)}
        if args.group:
            rest = label(m).split(".")
            if len(rest) > 1:  # nested under a sub-package
                d["group"] = "/".join(rest[:-1])  # full sub-package path -> nested boxes
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
