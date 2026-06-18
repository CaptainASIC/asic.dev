# Diagram types

Source of truth for the six diagram types and the type-selection heuristic. A diagram **type**
is the structural layout (shapes, edges, layout direction); a style **preset** (see
`style-presets.md`) is the visual look layered on top. Diagram-type styles set structural
keywords (e.g. ERD's `shape=table;childLayout=tableLayout`); the active preset layers
colour/font/edge on top, preserving those structural keywords.

## Type selection

Resolve the type once, per invocation, from the prompt:

1. **Explicit naming wins.** "draw an ERD", "sequence diagram", "flowchart of…", "UML class
   diagram", "architecture diagram", "neural net diagram" → use that type directly.
2. **Else infer from intent:**
   - data model / entities / relations / tables / schema → **ERD**
   - classes / inheritance / methods / OOP structure → **UML class**
   - ordered interactions / messages over time / request-response flow → **sequence**
   - services / infra / network / deployment / system components → **architecture**
   - model / training / layers / tensors / network architecture → **ML/DL**
   - steps / decisions / process / "how does X work" → **flowchart**
3. **Default to architecture** when ambiguous and the subject is a system.

**Code-to-diagram mode is type-fixed**, not inferred:
- `pyclasses.py` → **UML class**
- the import extractors (`pyimports`/`jsimports`/`goimports`/`rustimports`) → **architecture**

## ERD (Entity-Relationship)

Entity tables connected by crow's-foot/ER-notation edges. Each table is a container; columns
are child rows.

| Element | Style | Notes |
|---|---|---|
| Table | `shape=table;startSize=30;container=1;collapsible=1;childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;strokeColor=#6c8ebf;fillColor=#dae8fc;` | Each table is a container |
| Row (column) | `shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;fillColor=none;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;fontSize=12;` | Child of table, `parent=tableId` |
| PK column | `fontStyle=1` on the row | Mark with `PK` prefix or key icon |
| FK relationship | `dashed=1;endArrow=ERmandOne;startArrow=ERmandOne;` | ER-notation (crow's-foot) arrows |

Layout: TB, tables spaced ~300px apart; group related tables vertically.

## UML class

Class boxes (3-section: title / attributes / methods) connected by inheritance and
association edges.

| Element | Style | Notes |
|---|---|---|
| Class box | `swimlane;fontStyle=1;align=center;startSize=26;html=1;` | 3-section box |
| Section separator | `line;strokeWidth=1;fillColor=none;align=left;verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=10;rotatable=0;labelPosition=left;points=[];portConstraint=eastwest;` | Between sections |
| Inheritance | `endArrow=block;endFill=0;` | Hollow triangle |
| Implementation | `endArrow=block;endFill=0;dashed=1;` | Dashed + hollow triangle |
| Composition | `endArrow=diamondThin;endFill=1;` | Filled diamond |
| Aggregation | `endArrow=diamondThin;endFill=0;` | Hollow diamond |

Layout: TB, classes ~250px apart; interfaces above implementations.

## Sequence

Lifelines (vertical dashed lines) with activation bars; messages are horizontal edges, time
flows top→bottom.

| Element | Style | Notes |
|---|---|---|
| Actor/Object | `shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;` | Lifeline with dashed vertical line |
| Sync message | `html=1;verticalAlign=bottom;endArrow=block;` | Solid line, filled arrowhead |
| Async message | `html=1;verticalAlign=bottom;endArrow=open;dashed=1;` | Dashed line, open arrowhead |
| Return message | `html=1;verticalAlign=bottom;endArrow=open;dashed=1;strokeColor=#999999;` | Grey dashed |
| Activation bar | `shape=umlFrame;whiteSpace=wrap;` on the lifeline | Narrow rectangle on the lifeline |

Layout: lifelines spaced ~200px apart horizontally; time flows top→bottom.

## Architecture

Services, databases, queues, gateways grouped into tiers (swimlane containers), connected by
orthogonal edges. Colour by role (see `shapes.md` palette).

| Element | Style | Notes |
|---|---|---|
| Layer/tier | `swimlane;startSize=30;` | Container: Client / API / Service / Data |
| Service | `rounded=1;whiteSpace=wrap;html=1;` + blue | |
| Database | `shape=cylinder3;whiteSpace=wrap;html=1;` + green | |
| Queue/Bus | `rounded=1;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;` | Yellow; place centrally for a hub |
| Gateway/LB | `rounded=1;` + orange (or an AWS4 resource icon) | |
| External | `rounded=1;dashed=1;fillColor=#f5f5f5;strokeColor=#666666;` | Dashed border |

Layout: TB or LR by tier count; ≥4 tiers → TB; centre hub nodes.

## ML / DL model

Layer blocks stacked top→bottom, coloured by layer type, with tensor-shape annotations.

| Element | Style | Notes |
|---|---|---|
| Layer block | `rounded=1;whiteSpace=wrap;html=1;` + type colour | Main building block |
| Input/Output | `fillColor=#d5e8d4;strokeColor=#82b366;` | Green |
| Conv / Pooling | `fillColor=#dae8fc;strokeColor=#6c8ebf;` | Blue |
| Attention / Transformer | `fillColor=#e1d5e7;strokeColor=#9673a6;` | Purple |
| RNN / LSTM / GRU | `fillColor=#fff2cc;strokeColor=#d6b656;` | Yellow |
| FC / Linear | `fillColor=#ffe6cc;strokeColor=#d79b00;` | Orange |
| Loss / Activation | `fillColor=#f8cecc;strokeColor=#b85450;` | Red/Pink |
| Skip connection | `dashed=1;endArrow=block;curved=1;` | Dashed curved arrow |

Tensor convention: annotate each layer with input/output dims in `(B, C, H, W)` or `(B, T, D)`
form as a second label line via `&#xa;` (e.g. `value="Conv2D&#xa;(B, 64, 32, 32)"`). Layout:
TB, layers ~150px apart; group encoder/decoder as swimlanes.

## Flowchart

Process steps and decision diamonds connected by labeled edges; flows top→bottom.

| Element | Style | Notes |
|---|---|---|
| Start/End | `ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;` | Green oval |
| Process | `rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;` | Blue rectangle |
| Decision | `rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;` | Yellow diamond |
| I/O | `shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#ffe6cc;strokeColor=#d79b00;` | Orange parallelogram |
| Subprocess | `rounded=0;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;` | Purple, double border |

Always label decision-branch edges (`value="Yes"` / `value="No"`). Layout: TB, ~200px
vertical gap; decisions branch LR and merge back to centre.
