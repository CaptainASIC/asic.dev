# Shape vocabulary & search

Read this when a diagram needs a **specific shape** — a cloud-provider icon (AWS/Azure/GCP),
a network/Cisco/Kubernetes symbol, a UML/BPMN/ER element, an electrical/P&ID part — or any
time you'd otherwise guess a `style=` string. Two ways to get a style:

1. **Search the official shape index** (`scripts/shapesearch.py`) — real draw.io palette
   shapes with their exact `style`, `w`, `h`. Use for branded/vendor icons and anything
   non-trivial. Always prefer a searched style over a hand-written `shape=mxgraph.*` guess —
   a wrong stencil name silently renders as a blank box.
2. **The cheatsheet below** — built-in shapes whose style strings are short and stable enough
   to write by hand.

## Searching shapes

```bash
python3 <this-skill-dir>/scripts/shapesearch.py "aws lambda" --limit 5
python3 <this-skill-dir>/scripts/shapesearch.py "uml actor" --json
```

Positional `query` is required (space-separated keywords). Flags: `--limit <int>`
(default 10), `--json`.

- Matching is tag-based with Soundex fuzziness and `camelCase`/digit splitting.
- Prints each match as `Title (WxH)` followed by its full `style=` string. With `--json`,
  emits `[{style,w,h,title}]`.
- Copy the `style` verbatim into an `mxCell`; use the reported `w`/`h` as the `mxGeometry`
  width/height (vendor icons have a fixed aspect ratio).
- Results rank by tag relevance with title matches bubbled up, but ranking is heuristic and
  many shapes share a title. Run with `--limit 5` and pick the row whose title and size match
  what you want rather than blindly taking #1.

```xml
<mxCell id="2" value="Lambda" style="<paste the searched style here>" vertex="1" parent="1">
  <mxGeometry x="40" y="40" width="78" height="78" as="geometry"/>
</mxCell>
```

Covered libraries: AWS (`aws3`/`aws4`), Azure, GCP, Cisco, Kubernetes, UML, BPMN, ER,
electrical, P&ID, mockup/wireframe, flowchart, network, and the general/basic sets.

## AI / LLM brand logos

draw.io's bundled libraries have no modern AI/LLM brand logos. `scripts/aiicons.py` resolves
a brand name (OpenAI, Claude, Gemini, Mistral, Llama, HuggingFace, Ollama, LangChain, …) to a
draw.io `image` style.

```bash
python3 <this-skill-dir>/scripts/aiicons.py "claude" --json     # CDN reference
python3 <this-skill-dir>/scripts/aiicons.py "openai" --embed     # self-contained
python3 <this-skill-dir>/scripts/aiicons.py --list               # all brands
```

Positional `query` is optional. Flags: `--limit <int>` (default 8), `--variant {color,mono,text}`
(default `color`), `--size <int>` (default 48), `--embed`, `--json`, `--list`.

- Picks the `color` variant by default; falls back to mono when a brand has no colour logo
  (e.g. OpenAI). Returns a square `image` style — use `--size` for both width and height.
- **Default references the icon by CDN URL** — draw.io needs network access when the diagram
  is rendered or opened; an offline export draws a blank box. Pass `--embed` to inline the SVG
  as a data URI (portable, renders offline, larger XML).
- Data stores common in RAG/LLM apps that the icon set lacks (Qdrant, Redis, Postgres, Mongo,
  Elasticsearch, Milvus, Supabase, Neo4j, ClickHouse, Kafka, …) resolve via a fallback CDN —
  same command, same output. A brand in neither set has no logo; use a cylinder
  (`shape=cylinder3;`) or `shapesearch.py "<name> database"`.

## Semantic color palette

Seven roles, fixed colours. Use these consistently so a reader can infer role from colour.

| Role | Colour | fillColor / strokeColor |
|---|---|---|
| Services | blue | `#dae8fc` / `#6c8ebf` |
| Databases | green | `#d5e8d4` / `#82b366` |
| Queues | yellow | `#fff2cc` / `#d6b656` |
| APIs | orange | `#ffe6cc` / `#d79b00` |
| Errors | red | `#f8cecc` / `#b85450` |
| External | grey | `#f5f5f5` / `#666666` |
| Security | purple | `#e1d5e7` / `#9673a6` |

An active style preset overrides these with its own palette (see `style-presets.md`).

## .drawio XML construction rules

- **Root cells.** `<root>` must open with `<mxCell id="0"/>` and `<mxCell id="1" parent="0"/>`.
  User shapes start at `id="2"`.
- **Parent.** Every user shape needs `parent="1"` (or the id of its container).
- **Edges must carry geometry.** Every edge `mxCell` must contain a child
  `<mxGeometry relative="1" as="geometry" />`. A self-closing edge cell renders nothing.

  ```xml
  <mxCell id="5" style="endArrow=classic;html=1;" edge="1" parent="1" source="2" target="3">
    <mxGeometry relative="1" as="geometry" />
  </mxCell>
  ```

- **Line breaks** in labels use `&#xa;`, never a literal `\n`.
- **Special characters** in `value` use XML entities: `&amp;` `&lt;` `&gt;` `&quot;`.
- **Multi-connection shapes** distribute entry/exit points across the perimeter — vary
  `exitX`/`entryX` (and the Y variants) per edge so connections fan out instead of stacking
  on one point.

## Cheatsheet — hand-writable styles

Combine with `whiteSpace=wrap;html=1;`.

### Common shapes (`shape=` keyword)

| Need | style |
|---|---|
| Rectangle / rounded box | `rounded=0;` / `rounded=1;` |
| Circle / ellipse | `ellipse;` (`aspect=fixed;` for a true circle) |
| Diamond (decision) | `rhombus;` |
| Cylinder (database) | `shape=cylinder3;` |
| Cloud | `cloud;` |
| Cube (3D) | `shape=cube;` |
| Sticky note | `shape=note;` |
| Document (curled bottom) | `shape=document;` |
| Folder | `shape=folder;` |
| Card (cut corner) | `shape=card;` |
| Process (double border) | `shape=process;` |
| Step / chevron | `shape=step;` |
| Parallelogram (I/O) | `shape=parallelogram;perimeter=parallelogramPerimeter;` |
| Trapezoid | `shape=trapezoid;perimeter=trapezoidPerimeter;` |
| Hexagon | `shape=hexagon;perimeter=hexagonPerimeter2;` |
| Manual input | `shape=manualInput;` |
| Data storage | `shape=dataStorage;` |
| Off-page connector | `shape=offPageConnector;` |
| Delay | `shape=delay;` |
| OR / XOR gate | `shape=or;` / `shape=xor;` |
| Block arrow | `shape=singleArrow;` / `shape=doubleArrow;` |
| Callout (speech bubble) | `shape=callout;` |

### UML primitives

| Element | style |
|---|---|
| Actor (stick figure) | `shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;` |
| Boundary | `shape=umlBoundary;` |
| Control | `shape=umlControl;` |
| Entity | `shape=umlEntity;` |
| Lifeline | `shape=umlLifeline;perimeter=lifelinePerimeter;container=1;` |
| Frame | `shape=umlFrame;` |
| Provided interface (lollipop) | `shape=lollipop;direction=south;` |
| Required interface | `shape=requires;direction=north;` |
| Component | `shape=component;` |

### Containers (parent-child; children use relative coords)

| Type | style | When |
|---|---|---|
| Invisible group | `group;pointerEvents=0;` | No border, no own connections |
| Titled swimlane | `swimlane;startSize=30;` | Visible title bar / has connections |
| Any shape as container | append `container=1;pointerEvents=0;` | Box without own connections |

### Edges

| Need | add to style |
|---|---|
| Orthogonal routing | `edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;` |
| Curved | `curved=1;` |
| No arrowhead | `endArrow=none;` |
| Open/thin arrow | `endArrow=open;` / `endArrow=classicThin;` |
| Dashed | `dashed=1;` (pattern via `dashPattern=8 8;`) |
| Flow animation | `flowAnimation=1;` |
| Label background | `labelBackgroundColor=#ffffff;` |

### Property knobs

- `fontStyle` is a bitmask: `1`=bold, `2`=italic, `4`=underline (add to combine).
- `direction=north|south|east|west` rotates in 90° steps; `rotation=<deg>` for free rotation.
- `gradientColor=#RRGGBB;` + `gradientDirection=north;` for a gradient fill.
- `sketch=1;` gives a hand-drawn look (prefer setting it via a style preset).
