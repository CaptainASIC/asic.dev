#!/usr/bin/env python3
"""Extract a Go module's package-import graph as autolayout graph JSON.

The Go counterpart to pyimports.py / jsimports.py. Reads the module path from
go.mod, walks the module, treats each directory of .go files as one package
(node = its import path), and records the intra-module package imports. Stdlib
and third-party imports are ignored. Transitive reduction is on by default so
the diagram stays readable.

  python3 goimports.py ./mymodule -o graph.json
  python3 autolayout.py graph.json -o diagram.drawio

Parsing is regex-based over `import` statements (single and block form),
which is enough for a structural package graph. *_test.go files and vendor/
are skipped.

Usage: python3 goimports.py <module_dir> [-o graph.json] [--direction TB|LR]
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

MODULE: re.Pattern[str] = re.compile(r"^module\s+(\S+)", re.MULTILINE)
BLOCK: re.Pattern[str] = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
SINGLE: re.Pattern[str] = re.compile(r'import\s+(?:[\w.]+\s+|_\s+)?"([^"]+)"')
QUOTED: re.Pattern[str] = re.compile(r'"([^"]+)"')


def module_path(root: str) -> str | None:
    """Read the module path declared in go.mod at the module root.

    Args:
        root: Path to the module directory containing go.mod.

    Returns:
        The declared module path, or None when go.mod is missing or has no
        module declaration.
    """
    gomod = os.path.join(root, "go.mod")
    if not os.path.exists(gomod):
        return None
    with open(gomod, encoding="utf-8", errors="ignore") as fh:
        m = MODULE.search(fh.read())
    return m.group(1) if m else None


def discover(root: str, modpath: str) -> dict[str, list[str]]:
    """Discover every intra-module package and its .go files.

    Args:
        root: Path to the module directory.
        modpath: The module's import path (from go.mod).

    Returns:
        A mapping of package import path -> list of .go file paths, one entry
        per directory of .go files.
    """
    root = os.path.abspath(root)
    pkgs: dict[str, list[str]] = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("vendor", "testdata") and not d.startswith(".")]
        gofiles = [
            os.path.join(dirpath, f)
            for f in files
            if f.endswith(".go") and not f.endswith("_test.go")
        ]
        if not gofiles:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        ip = modpath if rel == "." else f"{modpath}/{rel}"
        pkgs[ip] = gofiles
    return pkgs


def imports_of(files: list[str], modpath: str, pkgs: dict[str, list[str]]) -> set[str]:
    """Find the intra-module package imports referenced by a package's files.

    Args:
        files: The .go file paths belonging to one package.
        modpath: The module's import path (from go.mod).
        pkgs: Mapping of known package import paths to their files.

    Returns:
        The set of intra-module package import paths referenced by `files`.
    """
    found: set[str] = set()
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                src = fh.read()
        except OSError:
            # Reason: unreadable source file is bad data -- skip and continue.
            continue
        specs: list[str] = []
        for block in BLOCK.findall(src):
            specs += QUOTED.findall(block)
        specs += SINGLE.findall(src)
        for spec in specs:
            # Reason: an import is intra-module only when it equals the module
            # path or is prefixed by "<modpath>/" -- everything else is stdlib
            # or third-party and ignored.
            if (spec == modpath or spec.startswith(modpath + "/")) and spec in pkgs:
                found.add(spec)
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
    """Build and emit the Go package import graph as autolayout graph JSON.

    Returns:
        None. Writes the JSON graph to stdout or the output file, and logs
        progress to stderr.

    Raises:
        SystemExit: When go.mod is missing/has no module path, or when no Go
            packages are found under the module dir.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Go import graph -> autolayout graph JSON.")
    ap.add_argument("module", help="module directory (contains go.mod)")
    ap.add_argument("-o", "--output", help="output JSON path (default: stdout)")
    ap.add_argument("--direction", default="TB", choices=["TB", "LR"])
    ap.add_argument(
        "--group",
        action="store_true",
        help="group nodes into containers by top-level package dir",
    )
    ap.add_argument(
        "--no-reduce",
        action="store_true",
        help="keep every edge (skip transitive reduction)",
    )
    args = ap.parse_args()

    modpath = module_path(args.module)
    if not modpath:
        sys.exit(f"error: no go.mod with a module path found in {args.module}")
    pkgs = discover(args.module, modpath)
    if not pkgs:
        sys.exit(f"error: no Go packages found under {args.module}")
    edges = sorted(
        {
            (ip, t)
            for ip, files in pkgs.items()
            for t in imports_of(files, modpath, pkgs)
            if t != ip
        },
    )
    raw = len(edges)
    if not args.no_reduce:
        edges = transitive_reduce(list(pkgs), edges)
    # Drop the module prefix from labels for readability; ids stay full.
    strip = modpath + "/"

    def label(ip: str) -> str:
        """Strip the module prefix from an import path for display."""
        return ip[len(strip) :] if ip.startswith(strip) else os.path.basename(ip)

    def node(ip: str) -> dict[str, str]:
        """Build the node dict for an import path, optionally with a group."""
        d = {"id": ip, "label": label(ip)}
        if args.group:
            rest = label(ip).split("/")
            if len(rest) > 1:  # nested under a sub-package
                d["group"] = "/".join(rest[:-1])  # full sub-package path -> nested boxes
        return d

    graph = {
        "direction": args.direction,
        "nodes": [node(ip) for ip in pkgs],
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
    logger.info("%d packages, %d edges%s", len(pkgs), len(edges), note)


if __name__ == "__main__":
    main()
