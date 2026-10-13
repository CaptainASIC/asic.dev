---
name: diagram
description: Generate editable draw.io architecture, network, and system diagrams from a description — or visualize an existing repo's structure. Plans a layout, writes a .drawio file to docs/diagrams/, exports PNG/SVG/PDF via the draw.io desktop CLI, vision-self-checks for overlaps/clipping, iterates with you, and offers to embed the result into a PRP/README. Use when the user says "draw a diagram", "diagram this architecture", "draw the network", "visualize this codebase/module structure", "make a flowchart/ERD/sequence/UML diagram", or invokes /diagram. Requires the draw.io desktop CLI (brew install --cask drawio); fails fast with the install command and a browser fallback if absent.
---

# diagram

Turn a description — or an existing codebase — into an editable `.drawio` file plus a rendered
image, via the native draw.io desktop CLI. Hand-place small styled diagrams; auto-lay-out large
graphs. Self-checks the render, iterates with the user, exports the final formats.

Ported and adapted from [Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill)
(MIT, tag `v1.14.0`) — see `NOTICE.md`. Detail lives in `references/`; read each on demand.

## Invoking the scripts

All eleven helper scripts run on the ambient `python3` (no project venv), by absolute path:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/<name>.py" …
```

Claude Code substitutes `${CLAUDE_SKILL_DIR}` with this skill's directory for both the plugin
install and the dev-mode symlink. Never use a `${VAR:-default}` form: only the bare `${CLAUDE_*}`
token is substituted, and the shell never has `CLAUDE_PLUGIN_ROOT` set. In the commands below
`<S>` stands for `"${CLAUDE_SKILL_DIR}"`.

## Output location

Default output dir is **`docs/diagrams/`** at the repo root (`mkdir -p` it). Write both the
`.drawio` source and the rendered image there so the editable source is committed beside the
picture. Honor any explicit path the user gives; never write outside the repo without one.

## Pipeline

1. **Resolve the style preset.** `default` is active unless the user names a preset ("use the
   corporate style", "draw it hand-drawn") or passes a `style=<name>` keyword. The named preset
   wins, else `default`. Resolution is per-invocation from the prompt — no persisted state. Apply
   the preset's style strings to shapes/edges. Built-in presets live in `styles/built-in/`; see
   `references/style-presets.md`.
2. **Select the diagram type.** One of: ERD, UML class, sequence, architecture, ML/DL, flowchart.
   Explicit naming wins ("draw an ERD", "sequence diagram", "flowchart of…"); else infer from
   intent (entities/relations → ERD; classes/inheritance → UML class; ordered messages over time →
   sequence; services/infra/network → architecture; model/training/layers → ML/DL; steps/decisions
   → flowchart); else default to **architecture** for a system subject. Emit per that type's
   conventions in `references/diagram-types.md`.
3. **Check the draw.io binary** (see *CLI detection* below). Missing → fail fast with the install
   command + browser fallback.
4. **Generate the `.drawio` XML** to `docs/diagrams/<name>.drawio`. Hand-place small/styled
   diagrams; for large/layout-heavy graphs (>~15 nodes) use autolayout (see *Code-to-diagram* and
   `references/autolayout.md`). Obey the XML rules below. For vendor/branded shapes run
   `shapesearch.py`; for AI/LLM logos run `aiicons.py` (`references/shapes.md`).
5. **Lint:** `python3 <S>/scripts/validate.py docs/diagrams/<name>.drawio` — fix any dangling
   edges, duplicate/reserved ids, or broken parents before exporting.
6. **Export a preview PNG** (no `-e`, width-capped) and run the **vision self-check** (below).
7. **Show the preview + run the user feedback loop** (below).
8. **Final export** on approval; **offer to embed** the image (below).

## XML rules (hard checklist — validate.py enforces most)

- Root cells `id="0"` and `id="1"` are required; user shapes start at `id="2"`.
- Every shape needs `parent="1"` (or a container id).
- Every edge MUST contain a child `<mxGeometry relative="1" as="geometry" />` — a self-closing
  edge cell is invalid and renders nothing.
- Line breaks in labels use `&#xa;`, never literal `\n`.
- A shape with 2+ connections distributes entry/exit points across its perimeter (vary
  `exitX`/`entryX`) so edges don't stack.

See `references/shapes.md` for the shape vocabulary, the 7-color semantic palette, and containers.

## CLI detection & export commands

Resolve the binary name once and reuse it verbatim. Try in order: `drawio` → `draw.io` →
`/Applications/draw.io.app/Contents/MacOS/draw.io` → Windows `…\draw.io.exe`. The first that prints
`--version` is your binary.

```bash
# Preview (step 6) — NO -e, width-capped for the vision API's 2576px ceiling
drawio -x -f png --width 2000 -o docs/diagrams/<name>.png docs/diagrams/<name>.drawio

# Final PNG (step 8) — WITH -e (embeds editable XML), then repair the truncated IEND chunk
drawio -x -f png -e -s 2 -o docs/diagrams/<name>.drawio.png docs/diagrams/<name>.drawio
python3 <S>/scripts/repair_png.py docs/diagrams/<name>.drawio.png

# SVG / PDF (vector — no IEND repair needed)
drawio -x -f svg -o docs/diagrams/<name>.svg docs/diagrams/<name>.drawio
drawio -x -f pdf -o docs/diagrams/<name>.pdf docs/diagrams/<name>.drawio
```

Do not pass `-e` on the preview — its embedded chunk makes the vision API reject the PNG. Always run
`repair_png.py` after a `-e` PNG export.

**Missing CLI — fail fast, then fall back.** If no binary resolves, tell the user:
`brew install --cask drawio`. Then offer the browser fallback: deliver the `.drawio` XML and a
diagrams.net URL via `python3 <S>/scripts/encode_drawio_url.py docs/diagrams/<name>.drawio`
(`--edit` for an editable editor URL). When the CLI is unavailable there is no PNG to read, so the
vision self-check is skipped. macOS sandbox crash → treat the CLI as unavailable, use the fallback.

## Vision self-check (step 6)

Agent-driven (no script). **Skippable:** skip when the user wants speed, when the diagram is trivial
(≤ ~5 shapes), or when no PNG was produced (browser-fallback path). Default on for non-trivial
diagrams.

- **Procedure.** Read the preview PNG; inspect against the defect list; if defects found, apply
  targeted XML edits, re-export the preview, re-check.
- **Defect criteria:** overlapping shapes; labels clipped by a shape border or the canvas edge;
  edges stacked on one perimeter point instead of distributed; edges crossing unrelated shapes; a
  node off-canvas. Anything else is *not* a self-check defect — it is feedback-loop material.
- **Stop condition:** stop when a round finds none of those defects, OR the **2-round** cap is
  reached — whichever first. After the cap, surface any remaining defects in the feedback loop.

## User feedback loop (step 7)

Distinct from the self-check (which auto-fixes render defects): this is the user reviewing the
shown preview.

- **Trigger.** After the self-check stops and the preview is shown, ask whether it needs changes
  ("Looks good, or want any changes?").
- **Round count.** Cap at **2** rounds for this MVP. Each round = user names changes → apply
  targeted XML edits → re-export the preview → show again.
- **Stop condition.** Proceed to final export when the user approves / wants no more changes, OR the
  2-round cap is reached — then export with the current diagram rather than looping further.

## Embed offer (step 8)

After the final export, offer to insert a markdown image link into an open PRP/README the user
names — format `![<title>](docs/diagrams/<name>.png)`. Output-and-offer; do not edit the user's
docs without their go-ahead.

## Code-to-diagram mode

"Visualize this repo/module" → extract the graph, autolayout it, then run the same export/
self-check/feedback pipeline. Pick the extractor by language; type is fixed (imports → architecture,
classes → UML class):

```bash
python3 <S>/scripts/pyimports.py   <dir> [--group] [--no-reduce] -o graph.json   # Python imports
python3 <S>/scripts/pyclasses.py   <dir> [--group] -o graph.json                  # Python classes → UML
python3 <S>/scripts/jsimports.py   <dir> -o graph.json                            # JS/TS imports
python3 <S>/scripts/goimports.py   <dir> -o graph.json                            # Go packages
python3 <S>/scripts/rustimports.py <dir> -o graph.json                            # Rust modules
python3 <S>/scripts/autolayout.py  graph.json -o docs/diagrams/<name>.drawio      # Graphviz layout
```

`autolayout.py` needs Graphviz (`dot`); if absent it exits non-zero with a clear message — fall back
to hand-placement and tell the user. See `references/autolayout.md`.

## References

- `references/diagram-types.md` — the six types, per-type emission, the selection heuristic.
- `references/shapes.md` — `shapesearch.py`/`aiicons.py`, the color palette, XML rules.
- `references/style-presets.md` — default/corporate/handdrawn + the resolution mechanism.
- `references/autolayout.md` — when/how to autolayout, transitive reduction, grouping.
- `references/troubleshooting.md` — CLI resolution, sandbox fallback, render-bug fixes.
