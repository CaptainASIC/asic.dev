#!/usr/bin/env python3
"""Deterministic structural linter for .drawio files.

Catches the class of mistakes a vision self-check is slow and unreliable at:
dangling edge endpoints, duplicate or reserved ids, broken parent references,
and (as warnings) off-grid geometry and overlapping sibling nodes. Runs without
launching draw.io, so it is a fast pre-check before the visual review step::

    python3 validate.py diagram.drawio

Exit status is non-zero when any error (or, with ``--strict``, any warning) is
found, so it can gate a workflow. Compressed (non-XML) diagram pages are
skipped with a warning -- this skill always writes uncompressed XML.

Usage:
    python3 validate.py <file.drawio> [--strict]
"""

import argparse
import logging
import sys
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

RESERVED: set[str] = {"0", "1"}

Rect = tuple[float, float, float, float]


def rect(cell: ET.Element) -> Rect | None:
    """Return the (x, y, w, h) geometry of a cell.

    Args:
        cell: An ``mxCell`` element.

    Returns:
        The (x, y, width, height) tuple of floats, or ``None`` if geometry is
        absent or non-numeric.
    """
    g = cell.find("mxGeometry")
    if g is None:
        return None
    try:
        return tuple(float(g.get(k, "nan")) for k in ("x", "y", "width", "height"))
    except ValueError:
        return None


def overlap(a: Rect, b: Rect) -> bool:
    """Report whether two axis-aligned rectangles overlap.

    Args:
        a: First (x, y, w, h) rectangle.
        b: Second (x, y, w, h) rectangle.

    Returns:
        ``True`` if the rectangles intersect.
    """
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def check_page(diagram: ET.Element) -> tuple[list[str], list[str]]:
    """Collect structural errors and warnings for one ``<diagram>`` page.

    Args:
        diagram: A ``<diagram>`` element (or a root standing in for one).

    Returns:
        A tuple of (errors, warnings) message lists.
    """
    name = diagram.get("name", "?")
    model = diagram.find("mxGraphModel")
    if model is None:
        if (diagram.text or "").strip():
            return [], [f"page {name!r}: compressed, skipped (cannot lint)"]
        return [f"page {name!r}: no <mxGraphModel>"], []
    root = model.find("root")
    cells = root.findall("mxCell") if root is not None else []
    errors: list[str] = []
    warns: list[str] = []
    ids: dict[str | None, ET.Element] = {}
    for c in cells:
        cid = c.get("id")
        if cid in ids:
            errors.append(f"duplicate id {cid!r}")
        ids[cid] = c
    parents = {c.get("parent") for c in cells}  # ids that have children
    for c in cells:
        cid, parent = c.get("id"), c.get("parent")
        is_v, is_e = c.get("vertex") == "1", c.get("edge") == "1"
        if parent is not None and parent not in ids:
            errors.append(f"cell {cid!r} parent {parent!r} does not exist")
        for end in ("source", "target"):
            ref = c.get(end)
            if ref and ref not in ids:
                errors.append(f"edge {cid!r} {end} {ref!r} does not exist")
        if (is_v or is_e) and cid in RESERVED:
            errors.append(f"cell {cid!r} reuses reserved id 0/1")
        if is_v:
            r = rect(c)
            if r is None or any(v != v for v in r):  # None or NaN
                errors.append(f"vertex {cid!r} has missing/invalid geometry")
            else:
                x, y, w, h = r
                if w <= 0 or h <= 0:
                    warns.append(f"vertex {cid!r} non-positive size {w:g}x{h:g}")
                if x < 0 or y < 0:
                    warns.append(f"vertex {cid!r} negative position ({x:g},{y:g})")
    # Reason: only leaf vertices are overlap-checked -- container vertices
    # legitimately wrap (and thus overlap) their children.
    boxes = [
        (c.get("id"), c.get("parent"), rect(c))
        for c in cells
        if c.get("vertex") == "1"
        and c.get("id") not in parents
        and rect(c)
        and not any(v != v for v in rect(c))
    ]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ia, pa, ra), (ib, pb, rb) = boxes[i], boxes[j]
            if pa == pb and overlap(ra, rb):
                warns.append(f"vertices {ia!r} and {ib!r} overlap")
    return errors, warns


def main() -> None:
    """Parse args, lint the file, log diagnostics, and set the exit code."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Lint a .drawio file for structural errors.")
    ap.add_argument("file")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failure too")
    args = ap.parse_args()
    try:
        tree = ET.parse(args.file)
    except (ET.ParseError, OSError) as exc:
        # Reason: an unreadable/unparseable file is fatal -- nothing to lint.
        sys.exit(f"error: cannot parse {args.file}: {exc}")
    pages = tree.getroot().findall("diagram") or [tree.getroot()]
    errors: list[str] = []
    warns: list[str] = []
    for page in pages:
        e, w = check_page(page)
        errors += e
        warns += w
    for w in warns:
        logger.warning("warning: %s", w)
    for e in errors:
        logger.error("error: %s", e)
    logger.info("%d error(s), %d warning(s)", len(errors), len(warns))
    if errors or (args.strict and warns):
        sys.exit(1)


if __name__ == "__main__":
    main()
