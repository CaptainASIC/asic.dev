#!/usr/bin/env python3
"""Extract a JS/TS project's module-import graph as autolayout graph JSON.

The JavaScript/TypeScript counterpart to pyimports.py: walks a source
directory, scans each module for static and dynamic import specifiers
(`import`/`export ... from`, `require()`, `import()`), keeps only the
intra-project edges (relative specifiers that resolve to a file under the
root), and applies transitive reduction so the diagram stays readable.

  python3 jsimports.py src -o graph.json
  python3 autolayout.py graph.json -o diagram.drawio

Resolution is path-based: relative specifiers are resolved against the
importing file's directory, trying the .ts/.tsx/.js/.jsx/.mjs/.cjs extensions
and directory index files. Bare specifiers (node_modules packages such as
"react") are ignored. Scanning is regex-based rather than a full parser, so a
specifier inside a comment or string literal is counted in rare cases.

Usage: python3 jsimports.py <src_dir> [-o graph.json] [--direction TB|LR]
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

EXTS: tuple[str, ...] = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# Reason: regex-based scan (not a full parser) -- matches import/export...from,
# side-effect import, require(), and dynamic import(); each form lands in its
# own capture group so the matched specifier is group(1)..group(4).
SPEC: re.Pattern[str] = re.compile(
    r"(?:import|export)\b[^'\";]*?\bfrom\s*['\"]([^'\"]+)['\"]"  # import/export ... from "x"
    r"|import\s*['\"]([^'\"]+)['\"]"  # import "x" (side effect)
    r"|require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"  # require("x")
    r"|import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",  # import("x") dynamic
)


def modid(path: str, root: str) -> str:
    """Compute a module id from a file path.

    Args:
        path: Absolute path to the source file.
        root: Absolute path to the project root.

    Returns:
        The path relative to root with its extension stripped and posix
        separators.
    """
    rel = os.path.relpath(path, root)
    for ext in EXTS:
        if rel.endswith(ext):
            rel = rel[: -len(ext)]
            break
    return rel.replace(os.sep, "/")


def discover(root: str) -> tuple[dict[str, str], str]:
    """Discover every source module under a root directory.

    Args:
        root: Path to the project source directory.

    Returns:
        A tuple of (module id -> absolute file path mapping, absolute root).
    """
    root = os.path.abspath(root)
    modules: dict[str, str] = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "node_modules" and not d.startswith(".")]
        for fn in files:
            if fn.endswith(EXTS) and not fn.endswith(".d.ts"):
                full = os.path.join(dirpath, fn)
                modules[modid(full, root)] = full
    return modules, root


def resolve(spec: str, importer: str, root: str, modules: dict[str, str]) -> str | None:
    """Resolve a relative import specifier to a known module id.

    Args:
        spec: The raw import specifier as written in source.
        importer: Absolute path of the importing file.
        root: Absolute path to the project root.
        modules: Mapping of known module ids to file paths.

    Returns:
        The resolved module id, or None when the specifier is external
        (bare specifier) or does not resolve to a known module.
    """
    # Reason: only relative specifiers can resolve intra-project; bare
    # specifiers (e.g. "react") are node_modules packages and are external.
    if not spec.startswith("."):
        return None
    base = os.path.normpath(os.path.join(os.path.dirname(importer), spec))
    candidates = [base + e for e in EXTS] + [os.path.join(base, "index" + e) for e in EXTS] + [base]
    for cand in candidates:
        mid = modid(cand, root)
        if mid in modules and modules[mid] != importer:
            return mid
    return None


def edges_of(mid: str, path: str, root: str, modules: dict[str, str]) -> set[str]:
    """Find the intra-project modules imported by a module.

    Args:
        mid: Module id of the importing module.
        path: Absolute path to the importing module's file.
        root: Absolute path to the project root.
        modules: Mapping of known module ids to file paths.

    Returns:
        The set of intra-project module ids that `mid` imports.
    """
    found: set[str] = set()
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            src = fh.read()
    except OSError:
        # Reason: unreadable source file is bad data -- skip and continue.
        return found
    for m in SPEC.finditer(src):
        spec = m.group(1) or m.group(2) or m.group(3) or m.group(4)
        target = resolve(spec, path, root, modules)
        if target and target != mid:
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


def common_dir(ids: list[str]) -> str:
    """Find the longest shared leading path segment across module ids.

    Args:
        ids: List of module ids.

    Returns:
        The shared leading directory path with a trailing slash (e.g.
        'src/'), or an empty string when there is no common prefix.
    """
    common: list[str] = []
    for parts in zip(*[m.split("/") for m in ids]):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    return "/".join(common) + "/" if common else ""


def main() -> None:
    """Build and emit the JS/TS import graph as autolayout graph JSON.

    Returns:
        None. Writes the JSON graph to stdout or the output file, and logs
        progress to stderr.

    Raises:
        SystemExit: When no JS/TS modules are found under the source dir.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="JS/TS import graph -> autolayout graph JSON.")
    ap.add_argument("src", help="source directory")
    ap.add_argument("-o", "--output", help="output JSON path (default: stdout)")
    ap.add_argument("--direction", default="TB", choices=["TB", "LR"])
    ap.add_argument(
        "--group",
        action="store_true",
        help="group nodes into containers by top-level directory",
    )
    ap.add_argument(
        "--no-reduce",
        action="store_true",
        help="keep every edge (skip transitive reduction)",
    )
    args = ap.parse_args()

    modules, root = discover(args.src)
    if not modules:
        sys.exit(f"error: no JS/TS modules found under {args.src}")
    edges = sorted(
        {(m, t) for m, p in modules.items() for t in edges_of(m, p, root, modules)},
    )
    raw = len(edges)
    if not args.no_reduce:
        edges = transitive_reduce(list(modules), edges)
    strip = common_dir(list(modules))

    def label(m: str) -> str:
        """Strip the common directory prefix from a module id for display."""
        return (m[len(strip) :] if strip and m.startswith(strip) else m) or m

    def node(m: str) -> dict[str, str]:
        """Build the node dict for a module id, optionally with a group."""
        d = {"id": m, "label": label(m)}
        if args.group:
            rest = label(m).split("/")
            if len(rest) > 1:  # has a sub-directory
                d["group"] = "/".join(rest[:-1])  # full directory path -> nested boxes
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
