# Style presets

A style preset is the visual **look** of a diagram — palette, shape vocabulary, font, edge
style, extras. This is distinct from a diagram **type** (see `diagram-types.md`), which is the
structural **layout**. A preset never changes which shapes exist or how they connect; it
restyles them. Both resolve independently per invocation.

## The three built-in presets

Backed by `styles/built-in/{default,corporate,handdrawn}.json` in the skill.

### default

The standard draw.io look. Pastel palette (blue `#dae8fc`, green `#d5e8d4`, yellow `#fff2cc`,
orange `#ffe6cc`, red `#f8cecc`, grey `#f5f5f5`, purple `#e1d5e7`), Helvetica 12, rounded
service boxes, orthogonal rounded edges with a classic filled arrow. No sketch, stroke
width 1.

### corporate

Crisper, higher-contrast look for slide decks. Saturated palette (blue `#1565c0` on
`#e3f2fd`, etc.), Arial 11, **square** corners (`rounded=0` for service/queue/external),
orthogonal **non-rounded** edges. Dashes async/optional flows. No sketch, stroke width 1.

### handdrawn

Informal sketch look. Warm earthy palette (orange `#b8651e` on `#ffe4b5`, etc.), Helvetica
12, rounded boxes, **curved** edges, `sketch=1` on every cell, stroke width 2. Dashes
optional flows.

## Selection mechanism (source of truth)

The skill holds no persisted state — the active preset is resolved per-invocation from the
prompt:

1. **A named preset wins.** If the user names one — "use the corporate style", "draw it
   hand-drawn" — or passes a `style=<name>` keyword in the prompt, that preset is active.
2. **Otherwise `default`.**

There is no global/sticky default; each invocation re-resolves from its own prompt. Custom
user presets are future work — only the three built-ins exist today.

## Applying a preset

When a preset is active, it replaces the built-in palette, shape keywords, edge defaults, and
font for this diagram. Do not mix in values from the default conventions.

**Colour.** For each role a shape plays (service / database / queue / gateway / error /
external / security), resolve `preset.roles[role]` → a palette slot name → `preset.palette[slot]`
for the `(fillColor, strokeColor)` pair. Canonical slots: `service→primary`,
`database→success`, `queue→warning`, `gateway→accent`, `error→danger`, `external→neutral`,
`security→secondary`.

**Decision/container shapes** have no role mapping:
- Decision (rhombus) → `preset.palette.warning`.
- Container (swimlane) → the slot matching the tier it represents (e.g. a Services tier →
  `primary`, a Data tier → `success`); default `primary`.

**Shape keywords.** Use `preset.shapes[role]` as the prefix of the vertex style string. The
six named keys are `service`, `database`, `queue`, `decision`, `external`, `container`. Roles
`gateway`, `error`, `security` reuse `preset.shapes.service`.

**Edges.** Base style is `preset.edges.style`; append `preset.edges.arrow`. Per-edge routing
keys (`exitX`/`entryX`/…) are still added by the routing rules. If the flow matches a token in
`preset.edges.dashedFor`, append `;dashed=1`.

**Fonts.** Append `fontFamily=<preset.font.fontFamily>;fontSize=<preset.font.fontSize>` to
every vertex style. Container/swimlane titles additionally get
`fontSize=<preset.font.titleFontSize>;fontStyle=1` when `preset.font.titleBold` is true.

**Extras.**
- `preset.extras.sketch === true` → append `sketch=1` to every vertex and edge style.
- `preset.extras.globalStrokeWidth !== 1` → append `strokeWidth=<n>` to every vertex and edge
  style.

## Interaction with diagram types

A diagram-type's structural keywords always survive (e.g. ERD tables rely on
`shape=table;startSize=30;container=1;childLayout=tableLayout;...`). Keep those, then layer
the preset's colour/font/edge/extras on top. When a diagram-type hardcodes a colour
(`fillColor=#dae8fc`) that conflicts with the preset, the preset's colour wins — **except**
`fillColor=none`, which is structural and must not be replaced.
