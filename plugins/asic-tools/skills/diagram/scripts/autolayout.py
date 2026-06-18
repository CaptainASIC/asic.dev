#!/usr/bin/env python3
"""Auto-layout a logical graph into draw.io XML using Graphviz.

Minimal layout pass for the drawio skill: takes a graph (nodes + edges as
JSON), runs ``dot`` to position the nodes, and emits a .drawio file with the
mxGeometry x/y filled in. draw.io routes the edges itself (orthogonal style).
This removes the manual-coordinate ceiling for medium/large diagrams.

Input JSON:
  {
    "direction": "TB",          # TB (top-bottom, default) or LR (left-right)
    "nodes": [
      {"id": "a", "label": "Service A", "style": "rounded=1;...",
       "width": 120, "height": 60}
    ],
    "edges": [
      {"source": "a", "target": "b", "label": "calls"}
    ]
  }
Only "id" is required per node; label defaults to id and style/width/height
have defaults. Node ids must be unique and must not be "0" or "1" (reserved
for the draw.io root cells). Requires Graphviz ``dot`` on PATH.

Usage: python3 autolayout.py graph.json [-o diagram.drawio]
"""

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
from typing import Any
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

# Type aliases for the layout data structures threaded between functions.
# GroupTree fields are (gpath, direct, children, ordered) — see group_tree().
GroupPath = tuple[str, ...]
GroupTree = tuple[
    dict[str, GroupPath],
    dict[GroupPath, list[str]],
    dict[GroupPath, list[GroupPath]],
    list[GroupPath],
]
NodePos = dict[str, tuple[float, float]]
EdgePoints = dict[tuple[str, str], list[tuple[float, float]]]

DEFAULT_W: int = 120
DEFAULT_H: int = 60
NODE_STYLE: str = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
EDGE_STYLE: str = "html=1;rounded=0;"
GROUP_STYLE: str = (
    "rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#999999;"
    "verticalAlign=top;fontStyle=2;dashed=1;"
)
# Group colours come from the skill's own palette (styles/built-in/default.json)
# so there is a single source of truth, not a second list baked in here. When a
# grouped graph is laid out, each top-level group takes the next colour (cycled
# in a fixed, harmonious role order) so related modules read as a coloured
# cluster. Nodes that carry their own `style` keep it; only styleless grouped
# nodes are tinted. Disable with --mono.
_PALETTE_ORDER: list[str] = [
    "primary",
    "success",
    "accent",
    "secondary",
    "warning",
    "danger",
    "neutral",
]
_PALETTE_FILE: str = os.path.join(
    os.path.dirname(__file__), "..", "styles", "built-in", "default.json"
)
_FALLBACK_PALETTE: list[tuple[str, str]] = [
    ("#dae8fc", "#6c8ebf"),
    ("#d5e8d4", "#82b366"),
    ("#ffe6cc", "#d79b00"),
    ("#e1d5e7", "#9673a6"),
    ("#fff2cc", "#d6b656"),
    ("#f8cecc", "#b85450"),
]


def load_palette() -> list[tuple[str, str]]:
    """Load the ordered (fill, stroke) palette from the default preset.

    Returns:
        Ordered list of (fillColor, strokeColor) pairs taken from the default
        preset's palette, or :data:`_FALLBACK_PALETTE` if the preset file
        cannot be read or parsed.
    """
    try:
        with open(_PALETTE_FILE, encoding="utf-8") as fh:
            pal = json.load(fh)["palette"]
        colors = [(pal[r]["fillColor"], pal[r]["strokeColor"]) for r in _PALETTE_ORDER if r in pal]
        if colors:
            return colors
    except (OSError, KeyError, ValueError):
        pass
    return _FALLBACK_PALETTE


PALETTE: list[tuple[str, str]] = load_palette()
# Uniform container padding; the title sits in the top pad (verticalAlign=top).
# dot's cluster margin is set to this same value so each container box equals
# dot's cluster box — which dot guarantees never overlaps, at any nesting depth.
GROUP_PAD: int = 24


def attr(value: Any) -> str:
    """Escape a value for use inside an XML double-quoted attribute.

    Args:
        value: Any value; stringified before escaping.

    Returns:
        The XML-escaped string with double quotes encoded as ``&quot;``.
    """
    return escape(str(value), {'"': "&quot;"})


def snap(value: float, grid: int = 10) -> int:
    """Snap a coordinate to the layout grid.

    Args:
        value: Coordinate to align.
        grid: Grid spacing the skill uses everywhere (multiples of 10).

    Returns:
        The nearest integer multiple of ``grid``.
    """
    return int(round(value / grid) * grid)


def group_tree(nodes: list[dict[str, Any]]) -> GroupTree:
    """Parse hierarchical ``group`` paths ("a/b") into a container tree.

    Args:
        nodes: Node dicts, each optionally carrying a ``group`` path string.

    Returns:
        A 4-tuple ``(gpath, direct, children, ordered)`` where:
          - ``gpath[node_id]`` is the tuple of path segments (the node's
            deepest container);
          - ``direct[path]`` is node ids whose group is exactly this path;
          - ``children[path]`` is child container paths;
          - ``ordered`` is all container paths, shallow-to-deep (stable).
    """
    gpath: dict[str, tuple[str, ...]] = {}
    direct: dict[tuple[str, ...], list[str]] = {}
    paths: set[tuple[str, ...]] = set()
    for node in nodes:
        g = node.get("group")
        if g is None or str(g).strip("/") == "":
            continue
        t = tuple(str(g).strip("/").split("/"))
        gpath[node["id"]] = t
        direct.setdefault(t, []).append(node["id"])
        for k in range(1, len(t) + 1):
            paths.add(t[:k])
    children: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    for p in sorted(paths):
        if len(p) > 1:
            children.setdefault(p[:-1], []).append(p)
    ordered = sorted(paths, key=lambda p: (len(p), p))
    return gpath, direct, children, ordered


def build_dot(graph: dict[str, Any]) -> str:
    """Build a Graphviz ``dot`` source string for the input graph.

    Args:
        graph: Parsed input graph with ``nodes`` (required), optional
            ``edges`` and ``direction``.

    Returns:
        A complete ``digraph`` source string ready to feed to ``dot``.
    """
    rankdir = "LR" if str(graph.get("direction", "TB")).upper() == "LR" else "TB"
    # Reason: splines=ortho makes dot route edges as orthogonal polylines; we
    # replay those bends as draw.io waypoints so edges go around nodes, not
    # through them.
    lines = [f"digraph G {{ rankdir={rankdir}; splines=ortho; node [shape=box fixedsize=true];"]
    # Reason: group nodes into (possibly nested) clusters so dot keeps each
    # group together; a node's first appearance fixes its cluster, so list
    # members before the size attributes. The cluster margin reserves room for
    # the padded container boxes we draw below so neighbouring boxes do not
    # overlap.
    _, direct, children, ordered = group_tree(graph["nodes"])
    cidx = {p: i for i, p in enumerate(ordered)}

    def emit_cluster(p: tuple[str, ...], pad: str) -> None:
        """Append a (possibly nested) ``subgraph cluster_*`` block to ``lines``.

        Args:
            p: Container path to emit.
            pad: Current indentation prefix.
        """
        lines.append(f"{pad}subgraph cluster_{cidx[p]} {{ margin={GROUP_PAD};")
        for c in children.get(p, []):
            emit_cluster(c, pad + "  ")
        lines.extend(f'{pad}  "{m}";' for m in direct.get(p, []))
        lines.append(pad + "}")

    for root in [p for p in ordered if len(p) == 1]:
        emit_cluster(root, "")
    for node in graph["nodes"]:
        # Reason: pass our pixel sizes to dot as inches (72 px/in) so it lays
        # out at the real on-canvas size.
        w = node.get("width", DEFAULT_W) / 72.0
        h = node.get("height", DEFAULT_H) / 72.0
        lines.append(f'"{node["id"]}" [width={w:.4f} height={h:.4f}];')
    for edge in graph.get("edges", []):
        lines.append(f'"{edge["source"]}" -> "{edge["target"]}";')
    lines.append("}")
    return "\n".join(lines)


def layout(dot_src: str) -> tuple[float, NodePos, EdgePoints]:
    """Run ``dot -Tplain`` and parse node positions and edge routing.

    Node coords are inches (bottom-left origin); each edge's value is the list
    of orthogonal control points dot computed for routing, endpoints included.

    Args:
        dot_src: Graphviz ``dot`` source produced by :func:`build_dot`.

    Returns:
        A 3-tuple ``(height_in, pos, edges)`` where ``pos`` maps node id to
        ``(xc, yc)`` centre coordinates and ``edges`` maps ``(src, dst)`` to a
        list of ``(x, y)`` routing points.

    Raises:
        SystemExit: If Graphviz ``dot`` is not on PATH or the ``dot`` run fails.
    """
    try:
        proc = subprocess.run(
            ["dot", "-Tplain"],
            input=dot_src,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("error: Graphviz `dot` not found on PATH (brew install graphviz)")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: dot failed: {exc.stderr.strip()}")
    height = 0.0
    pos: NodePos = {}
    edges: EdgePoints = {}
    for line in proc.stdout.splitlines():
        tok = shlex.split(line)
        if not tok:
            continue
        if tok[0] == "graph":
            height = float(tok[3])  # graph scale width height
        elif tok[0] == "node":
            pos[tok[1]] = (float(tok[2]), float(tok[3]))  # node name x y ...
        elif tok[0] == "edge":  # edge tail head n x1 y1 ... xn yn
            n = int(tok[3])
            edges[(tok[1], tok[2])] = [
                (float(tok[4 + 2 * i]), float(tok[5 + 2 * i])) for i in range(n)
            ]
    return height, pos, edges


def group_style(stroke: str) -> str:
    """Build a container box style tinted with a group's colour.

    Args:
        stroke: Stroke/border colour (also used for the title font colour).

    Returns:
        A draw.io style string for a coloured, dashed container with a top title.
    """
    return (
        f"rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor={stroke};"
        f"fontColor={stroke};verticalAlign=top;fontStyle=2;dashed=1;"
    )


def to_drawio(
    graph: dict[str, Any],
    height: float,
    pos: NodePos,
    edge_pts: EdgePoints,
    color: bool = True,
) -> str:
    """Render the laid-out graph into a complete .drawio XML document.

    Args:
        graph: Parsed input graph.
        height: Graph height in inches (from :func:`layout`), used to flip the
            bottom-left dot origin to draw.io's top-left origin.
        pos: Node id to ``(xc, yc)`` centre coordinates in inches.
        edge_pts: ``(src, dst)`` to dot routing points (inches).
        color: Whether to tint top-level groups by palette (False = monochrome).

    Returns:
        The complete ``<mxfile>`` XML string.
    """
    nodes = graph["nodes"]
    # Absolute snapped rect for every placed node.
    rects: dict[str, tuple[int, int, int, int]] = {}
    for node in nodes:
        nid = node["id"]
        if nid not in pos:
            continue
        w, h = node.get("width", DEFAULT_W), node.get("height", DEFAULT_H)
        xc, yc = pos[nid]
        x = snap(xc * 72 - w / 2)
        # Reason: flip Y — dot's origin is bottom-left, draw.io's is top-left.
        y = snap((height - yc) * 72 - h / 2)
        rects[nid] = (x, y, w, h)
    # Parse the (possibly nested) group tree and assign each container a
    # collision-free id and a title (the path's last segment, or a member's
    # groupLabel).
    gpath, direct, children, ordered = group_tree(nodes)
    # Assign each top-level group a palette colour, in order of first appearance.
    top_order: list[str] = []
    for node in nodes:
        t = gpath.get(node["id"])
        if t and t[0] not in top_order:
            top_order.append(t[0])

    def gcolor(seg: str) -> tuple[str, str]:
        """Return the palette (fill, stroke) pair for a top-level group segment.

        Args:
            seg: First path segment of a group.

        Returns:
            The cycled (fill, stroke) palette pair for that group.
        """
        return PALETTE[top_order.index(seg) % len(PALETTE)]

    used = {n["id"] for n in nodes}
    label_override: dict[tuple[str, ...], str] = {}
    for node in nodes:
        if node["id"] in gpath and "groupLabel" in node:
            label_override.setdefault(gpath[node["id"]], str(node["groupLabel"]))
    gid: dict[tuple[str, ...], str] = {}
    glabel: dict[tuple[str, ...], str] = {}
    for i, p in enumerate(ordered):
        cid = f"group_{i}"
        while cid in used:  # never collide with a node id
            cid += "_"
        used.add(cid)
        gid[p] = cid
        glabel[p] = label_override.get(p, p[-1])
    # Container bounding box (members + nested children + uniform padding),
    # computed deepest-first so a parent can wrap its already-sized children.
    gbox: dict[tuple[str, ...], tuple[int, int, int, int]] = {}
    for p in sorted(ordered, key=len, reverse=True):
        xs = [
            (rects[m][0], rects[m][1], rects[m][0] + rects[m][2], rects[m][1] + rects[m][3])
            for m in direct.get(p, [])
            if m in rects
        ]
        xs += [
            (gbox[c][0], gbox[c][1], gbox[c][0] + gbox[c][2], gbox[c][1] + gbox[c][3])
            for c in children.get(p, [])
            if c in gbox
        ]
        if not xs:
            continue
        x0 = min(b[0] for b in xs) - GROUP_PAD
        y0 = min(b[1] for b in xs) - GROUP_PAD
        x1 = max(b[2] for b in xs) + GROUP_PAD
        y1 = max(b[3] for b in xs) + GROUP_PAD
        gbox[p] = (x0, y0, x1 - x0, y1 - y0)

    # Shift everything positive: a container's top padding can push its top edge
    # above the page origin. Only translates when something would be negative.
    absx = [r[0] for r in rects.values()] + [b[0] for b in gbox.values()]
    absy = [r[1] for r in rects.values()] + [b[1] for b in gbox.values()]
    dx = GROUP_PAD - min(absx) if absx and min(absx) < 0 else 0
    dy = GROUP_PAD - min(absy) if absy and min(absy) < 0 else 0

    def rebase(x: int, y: int, parent_path: tuple[str, ...] | None) -> tuple[int, int, str]:
        """Convert absolute coords to coords relative to a parent container.

        Args:
            x: Absolute x coordinate.
            y: Absolute y coordinate.
            parent_path: Parent container path, or None for a top-level cell.

        Returns:
            A 3-tuple ``(x, y, parent_id)``: coordinates relative to
            ``parent_path``'s box (or shifted by ``dx``/``dy`` if top-level)
            and the draw.io parent cell id.
        """
        if parent_path is None:
            return x + dx, y + dy, "1"
        px, py, _, _ = gbox[parent_path]
        return x - px, y - py, gid[parent_path]

    cells: list[str] = []
    # Containers shallow-first so each parent precedes its children.
    for p in ordered:
        if p not in gbox:
            continue
        gx, gy, gw, gh = gbox[p]
        x, y, parent = rebase(gx, gy, p[:-1] if len(p) > 1 else None)
        gstyle = group_style(gcolor(p[0])[1]) if color else GROUP_STYLE
        cells.append(
            f'        <mxCell id="{attr(gid[p])}" value="{attr(glabel[p])}" '
            f'style="{gstyle}" vertex="1" parent="{attr(parent)}">\n'
            f'          <mxGeometry x="{x}" y="{y}" width="{gw}" height="{gh}" as="geometry"/>\n'
            f"        </mxCell>"
        )
    for node in nodes:
        nid = node["id"]
        if nid not in rects:
            continue
        rx, ry, w, h = rects[nid]
        x, y, parent = rebase(rx, ry, gpath.get(nid) if gpath.get(nid) in gbox else None)
        if node.get("style"):
            style = node["style"]  # explicit style always wins
        elif color and nid in gpath:
            fill, stroke = gcolor(gpath[nid][0])  # tint styleless nodes by group
            style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        else:
            style = NODE_STYLE
        cells.append(
            f'        <mxCell id="{attr(nid)}" value="{attr(node.get("label", nid))}" '
            f'style="{style}" vertex="1" parent="{attr(parent)}">\n'
            f'          <mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>\n'
            f"        </mxCell>"
        )
    for i, edge in enumerate(graph.get("edges", [])):
        # Reason: drop the first/last points (they sit on the node borders,
        # where draw.io attaches anyway) and replay only the interior bends as
        # waypoints so edges route around nodes.
        interior = edge_pts.get((edge["source"], edge["target"]), [])[1:-1]
        if interior:
            points = "".join(
                f'<mxPoint x="{snap(x * 72) + dx}" y="{snap((height - y) * 72) + dy}"/>'
                for x, y in interior
            )
            geom = (
                f'<mxGeometry relative="1" as="geometry">'
                f'<Array as="points">{points}</Array></mxGeometry>'
            )
        else:
            geom = '<mxGeometry relative="1" as="geometry"/>'
        cells.append(
            f'        <mxCell id="e{i}" value="{attr(edge.get("label", ""))}" '
            f'style="{EDGE_STYLE}" edge="1" parent="1" '
            f'source="{attr(edge["source"])}" target="{attr(edge["target"])}">\n'
            f"          {geom}\n"
            f"        </mxCell>"
        )
    return (
        '<mxfile>\n  <diagram id="autolayout" name="Page-1">\n'
        '    <mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="850" pageHeight="1100" math="0" shadow="0">\n'
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        + "\n".join(cells)
        + "\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n"
    )


def main() -> None:
    """Parse args, lay out the input graph, and write/print the .drawio XML."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Auto-layout a graph JSON into draw.io XML.")
    ap.add_argument("input", help="graph JSON file")
    ap.add_argument("-o", "--output", help="output .drawio path (default: stdout)")
    ap.add_argument(
        "--mono",
        action="store_true",
        help="don't colour groups by palette (monochrome boxes)",
    )
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        graph = json.load(f)
    height, pos, edge_pts = layout(build_dot(graph))
    xml = to_drawio(graph, height, pos, edge_pts, color=not args.mono)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(xml)
        logger.info(
            "wrote %s (%d nodes, %d edges)",
            args.output,
            len(graph["nodes"]),
            len(graph.get("edges", [])),
        )
    else:
        sys.stdout.write(xml)


if __name__ == "__main__":
    main()
