#!/usr/bin/env python3
"""Extract a Python project's class-inheritance graph as autolayout graph JSON.

A finer-grained companion to pyimports.py: instead of module->module imports,
it emits one node per class and an edge from each subclass to the project base
classes it extends. With ``--group``, classes are boxed by their module (nested
by sub-package), so the result reads as an auto-generated class hierarchy::

    python3 pyclasses.py myproject --group -o graph.json
    python3 autolayout.py graph.json -o diagram.drawio

Only inheritance is resolved (statically reliable); base classes are matched
by name, preferring a class in the same module. External bases (object,
Exception, third-party) are ignored. This is a *class structure* view, not a
function-level call graph -- static call resolution in Python is unreliable, so
that is deliberately out of scope.

Usage:
    python3 pyclasses.py <project_dir> [-o graph.json] [--direction TB|LR]
                                       [--group] [--no-reduce]
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

    Qualifies module names with the package name when ``root`` is itself a
    package (mirrors pyimports.py).

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
            rel = os.path.relpath(os.path.join(dirpath, fn), root)[:-3]
            parts = rel.split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            parts = ([base] + parts) if base else parts
            if parts:
                modules[".".join(parts)] = os.path.join(dirpath, fn)
    return modules, base


def base_name(node: ast.expr) -> str | None:
    """Return the simple name of a base-class expression.

    Args:
        node: AST expression for a base class (``Foo`` or ``pkg.Foo``).

    Returns:
        The simple class name (``'Foo'``), or ``None`` for unsupported forms.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def classes_in(module: str, path: str) -> list[tuple[str, str, list[str]]]:
    """Extract the top-level classes of a module.

    Args:
        module: Dotted name of the module.
        path: File path of the module.

    Returns:
        List of (qualified_id, simple_name, [base names]) for each top-level
        class, or an empty list if the module cannot be parsed.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except SyntaxError:
        # Reason: a single unparseable module is bad data -- skip it and keep going.
        return []
    out: list[tuple[str, str, list[str]]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = [b for b in (base_name(b) for b in node.bases) if b]
            out.append((f"{module}.{node.name}", node.name, bases))
    return out


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
    """Parse args, build the inheritance graph, and emit autolayout graph JSON."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(
        description="Python class-inheritance graph -> autolayout graph JSON.",
    )
    ap.add_argument("project", help="package or project directory")
    ap.add_argument("-o", "--output", help="output JSON path (default: stdout)")
    ap.add_argument("--direction", default="TB", choices=["TB", "LR"])
    ap.add_argument(
        "--group",
        action="store_true",
        help="box classes by their module (nested by sub-package)",
    )
    ap.add_argument(
        "--no-reduce",
        action="store_true",
        help="keep every edge (skip transitive reduction)",
    )
    args = ap.parse_args()

    modules, base = discover(args.project)
    classes: dict[str, tuple[str, list[str]]] = {}  # qualified id -> (module, bases)
    by_name: dict[str, list[str]] = {}  # simple name -> [qualified ids]
    for mod, path in modules.items():
        for cid, name, bases in classes_in(mod, path):
            classes[cid] = (mod, bases)
            by_name.setdefault(name, []).append(cid)
    if not classes:
        sys.exit(f"error: no classes found under {args.project}")

    def resolve(name: str, module: str) -> str | None:
        """Resolve a base-class name to a qualified class id.

        Args:
            name: Simple base-class name.
            module: Module of the subclass, used to disambiguate.

        Returns:
            The qualified class id, or ``None`` if ambiguous/unknown.
        """
        cands = by_name.get(name, [])
        same = [c for c in cands if classes[c][0] == module]
        if same:
            # Reason: a same-module base wins so a local name shadows any
            # identically named class elsewhere in the project.
            return same[0]
        return cands[0] if len(cands) == 1 else None  # else only if unambiguous

    edges: set[tuple[str, str]] = set()
    for cid, (mod, bases) in classes.items():
        for b in bases:
            target = resolve(b, mod)
            if target and target != cid:
                edges.add((cid, target))
    sorted_edges = sorted(edges)
    raw = len(sorted_edges)
    if not args.no_reduce:
        sorted_edges = transitive_reduce(list(classes), sorted_edges)

    strip = base + "." if base else ""

    def short(m: str) -> str:
        """Strip the shared package prefix from a module name for display."""
        return m[len(strip) :] if strip and m.startswith(strip) else m

    def node(cid: str) -> dict[str, str]:
        """Build the graph node dict for class ``cid``."""
        # No hard-coded colour: autolayout tints nodes by their group (module),
        # so a grouped class hierarchy reads as coloured-by-module.
        d = {"id": cid, "label": cid.rsplit(".", 1)[1]}
        if args.group:
            mod = classes[cid][0]
            path = short(mod).replace(".", "/")  # module path -> nested boxes
            if path:
                d["group"] = path
        return d

    graph = {
        "direction": args.direction,
        "nodes": [node(cid) for cid in classes],
        "edges": [{"source": s, "target": t} for s, t in sorted_edges],
    }
    text = json.dumps(graph, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        logger.info("wrote %s", args.output)
    else:
        sys.stdout.write(text)
    note = "" if args.no_reduce else f" (reduced from {raw})"
    logger.info("%d classes, %d inheritance edges%s", len(classes), len(sorted_edges), note)


if __name__ == "__main__":
    main()
