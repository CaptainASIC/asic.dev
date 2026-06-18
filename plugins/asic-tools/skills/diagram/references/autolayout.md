# Auto-layout (Graphviz)

Use auto-layout when a diagram is large or layout-heavy — dependency/call graphs, code or
module structure, roughly **more than ~15 nodes** — where hand-placing `x`/`y` coordinates
is slow and overlap-prone. Describe the graph as JSON and let `scripts/autolayout.py` place
nodes and route edges via Graphviz, then continue the normal workflow on the produced
`.drawio`.

For small or carefully-styled diagrams, hand-place. Auto-layout trades fine control for scale.

## Dependency

Requires Graphviz `dot` on PATH:

```bash
brew install graphviz          # macOS
sudo apt install graphviz      # Debian/Ubuntu
```

The script exits with a clear message if `dot` is missing — fall back to hand-placed
coordinates in that case.

## Usage

```bash
python3 <this-skill-dir>/scripts/autolayout.py graph.json -o diagram.drawio
```

Flags: `-o`/`--output <path>` (output `.drawio`), `--mono` (disable group colouring).
It prints `wrote diagram.drawio (N nodes, M edges)` to stderr. Continue at the **Export
draft** step of the main workflow (preview PNG with `--width 2000`, self-check, review loop,
final export with `-e` + `repair_png.py`).

## Input format

```json
{
  "direction": "TB",
  "nodes": [
    {"id": "client", "label": "Web Client", "style": "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"},
    {"id": "gw", "label": "API Gateway", "group": "edge", "groupLabel": "Edge tier"},
    {"id": "db", "label": "User DB", "style": "shape=cylinder3;whiteSpace=wrap;html=1;", "width": 120, "height": 80, "group": "data"}
  ],
  "edges": [
    {"source": "client", "target": "gw", "label": "HTTPS"},
    {"source": "gw", "target": "db"}
  ]
}
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `direction` | no | `TB` | `TB` (top→bottom) or `LR` (left→right) — layout rank direction |
| `nodes[].id` | **yes** | — | Unique; must not be `0` or `1` (reserved draw.io root cells) |
| `nodes[].label` | no | the `id` | Display text; auto XML-escaped |
| `nodes[].style` | no | group colour, else blue | Any draw.io style string. Reuse role/shape styles from `diagram-types.md` and the active preset. An explicit style always wins over group tint |
| `nodes[].width` / `height` | no | `120` / `60` | Pixels; dot lays out at this real size |
| `nodes[].group` | no | none | Group key, or `/`-delimited path (`"core/db"`) for nested containers |
| `nodes[].groupLabel` | no | last path segment | Title on the node's deepest container (first node with the path wins) |
| `edges[].source` / `target` | **yes** | — | Must match node ids |
| `edges[].label` | no | empty | Edge text |

## How it places things

- Node positions come from `dot` (hierarchical layered layout), converted to draw.io pixels
  and snapped to the grid (multiples of 10).
- Edges use `splines=ortho`: dot's orthogonal route is replayed as draw.io waypoints, so
  edges route **around** nodes, not through them.
- The script does not know about style presets. Set each node's `style` to the preset's
  role/shape values before calling it.

## Nested-container module grouping

Give nodes a `group` key and the script wraps each group in a labeled container (dashed box,
title at top) and tells dot to keep that group's nodes together as a Graphviz cluster.
Grouped nodes become children of their container (`parent="<container>"`, relative
coordinates); ungrouped nodes stay at the top level. A flat hairball becomes a "boxes of
related modules" view.

**Nesting.** A `group` value with `/` separators builds nested containers: `"core/db"` puts
the node inside a `db` box that itself sits inside a `core` box. Every path prefix becomes a
container, so an arbitrarily deep package tree maps to nested boxes. A node can sit directly
in a parent box (`group: "core"`) alongside a sibling sub-box (`group: "core/db"`).

- **Colour by group.** Each top-level group is assigned a colour from
  `styles/built-in/default.json` (cycled in role order: blue → green → orange → purple →
  yellow → red → grey). A styleless node is tinted with its group's colour; the container
  border and title match. A node carrying its own `style` is left untouched. Pass `--mono`
  for dashed grey boxes and default-blue nodes.
- Each container box is the bounding box of its members plus uniform padding; the dot cluster
  margin matches, so boxes stay non-overlapping at any nesting depth.
- Containers are visual only — no edges of their own. Edges still connect node→node and route
  across containers normally.
- If a container's top padding would cross the page origin, the whole diagram shifts so
  nothing lands at a negative coordinate.

## Orthogonal edge routing

Edges are routed orthogonally (`splines=ortho`) by dot and replayed as draw.io waypoints.
Parallel edges between the same `(source, target)` pair share one route. Placement is
topological (dot minimises crossings), not semantic — re-export with the other `direction`
or hand-tune the produced `.drawio` if a node lands in an unwanted column.

## Validate before previewing

Run `scripts/validate.py` on the produced `.drawio` before the slower vision-based
self-check:

```bash
python3 <this-skill-dir>/scripts/validate.py diagram.drawio
```

It catches dangling edge endpoints, duplicate/reserved ids, broken parent references
(errors), plus off-grid/negative geometry and overlapping siblings (warnings) — without
launching draw.io. Exit status is non-zero on any error (or any warning with `--strict`), so
it can gate the workflow. Auto-layout output should pass clean; a failure means a malformed
input graph (e.g. an edge referencing a missing node id).

## Importers — visualize code structure

Bundled extractors turn a codebase into graph JSON ready for autolayout, making "visualize
this project" a two-step pipeline:

| Language | Script | Node = | Edge = |
|---|---|---|---|
| Python | `scripts/pyimports.py <dir>` | module / package (`ast`) | intra-project `import` / `from` |
| JS / TS | `scripts/jsimports.py <dir>` | source file | resolved relative `import`/`require()`/`import()` |
| Go | `scripts/goimports.py <dir>` | package (directory, via `go.mod`) | intra-module package import |
| Rust | `scripts/rustimports.py <dir>` | module (`.rs` file / `mod`) | intra-crate `use crate::`/`super::`/`self::` |
| Python (classes) | `scripts/pyclasses.py <dir>` | class (`ast`) | subclass → base (inheritance) |

```bash
python3 <this-skill-dir>/scripts/pyimports.py myproject -o graph.json
python3 <this-skill-dir>/scripts/autolayout.py graph.json -o diagram.drawio
```

All five extractors keep only intra-project edges (third-party/stdlib ignored), shorten node
labels (drop the shared prefix; ids stay fully qualified), and share these flags:
`-o`/`--output <path>`, `--direction {TB,LR}` (default `TB`), `--group`, `--no-reduce`.

- **pyimports.py**: if the directory is itself a package (`__init__.py` present), module names
  are package-qualified; nested subpackages are handled.
- **jsimports.py**: path-based resolution (tries source extensions and directory `index`
  files); `node_modules` and bare specifiers are skipped. Regex-based, not a full parser.
- **goimports.py**: reads `module` from `go.mod`; each directory of `.go` files is one
  package; `*_test.go` and `vendor/` are skipped.
- **rustimports.py**: each `.rs` file is a module; edges from `use` paths rooted at
  `crate::`/`super::`/`self::`. `std`/external crates and `target/` skipped. Regex-based —
  inline `mod { … }` blocks are not split out.
- **pyclasses.py**: one node per class, edges from each subclass to the project base classes
  it extends. Bases matched by name (preferring the same module); external bases (`object`,
  third-party) ignored. With `--group`, classes are boxed by module. Inheritance only — no
  call graphs.

## Transitive reduction

**Density reduction is on by default** and is the key to a readable result. Real import
graphs are dense; without reduction they render as a hairball. Each extractor applies
**transitive reduction** (Graphviz `tred` — drops edges already implied by a longer path).
On asyncio (33 modules / ~149 edges) this cuts to ~46 edges. Pass `--no-reduce` to keep every
edge.

`--group` assigns each node a container by its sub-package / directory path, so autolayout
boxes related modules together (nested when the path has depth) — the fastest way to turn a
large code graph into a tiered architecture view.

For any other language, produce the same graph JSON from any analyzer and feed it to
autolayout the same way.

## Limitations

- Placement is topological, not semantic.
- Import edges are static — extractors read static statements (not dynamic `importlib`,
  runtime `require`, or reflection); `pyclasses` resolves inheritance only.
- Parallel edges between the same pair share one route.
- Containers don't add edges — `group`/nesting only boxes nodes. For hand-built
  swimlane/architecture containers with their own connections, see SKILL.md.
