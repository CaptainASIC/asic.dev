# Troubleshooting

Read this when something looks wrong in the output (rendering, export, layout, edges) or when
a CLI invocation fails.

## draw.io binary resolution

The export CLI ships under several names. Resolve in this order, taking the first that exists:

1. `drawio` — Homebrew installs the binary without a dot (`brew install --cask drawio`). Use
   `drawio --version`, not `draw.io --version`.
2. `draw.io` — alternate name on some installs.
3. `/Applications/draw.io.app/Contents/MacOS/draw.io` — the dot-name binary inside the macOS
   `.app` bundle. Use the full path when neither name is on PATH.
4. `*.exe` — `draw.io.exe` on Windows.

`command not found: draw.io` after a Homebrew install almost always means you used the
dot-name; switch to `drawio`.

## macOS sandbox fallback

When the CLI cannot run under the macOS sandbox (no binary, sandboxed shell, GPU-less
headless), skip CLI export entirely. Use the browser fallback: encode the diagram into a
draw.io viewer/editor URL and open it.

```bash
URL=$(python3 <this-skill-dir>/scripts/encode_drawio_url.py --edit diagram.drawio)
open "$URL"
```

`encode_drawio_url.py` takes a single positional path; `--edit` produces an editable-URL
fragment. The whole diagram travels in the URL fragment, so no export binary is needed.

## Validate before export

Run `scripts/validate.py` on the `.drawio` before exporting — it is deterministic and catches
the structural bugs that waste an export/vision round-trip:

```bash
python3 <this-skill-dir>/scripts/validate.py diagram.drawio
python3 <this-skill-dir>/scripts/validate.py diagram.drawio --strict
```

Positional `file`; flag `--strict`. It reports dangling edge endpoints, duplicate/reserved
ids, and broken parent references as errors; off-grid/negative geometry and overlapping
siblings as warnings. Exit status is non-zero on any error (or any warning with `--strict`).

## Repair the final PNG

After a `-e` PNG export, run `repair_png.py` to fix the truncated IEND chunk that makes the
file fail to open in image viewers / vision APIs:

```bash
python3 <this-skill-dir>/scripts/repair_png.py diagram.drawio.png
```

Single positional path, no flags. draw.io's CLI emits `-e` PNGs with an 8-byte truncation at
IEND; SVG/PDF are unaffected. For the *preview* PNG, the simplest fix is to export without
`-e` (a truncated IEND also triggers vision 400 "Could not process image").

## Common render bugs

| Symptom | Fix |
|---|---|
| Missing `id="0"` / `id="1"` root cells | Always include both at the top of `<root>` |
| Shapes not connected | Edge `source`/`target` must match existing shape `id` values |
| Edge renders nothing (self-closing `mxCell`) | Use the expanded form with a child `<mxGeometry relative="1" as="geometry" />` |
| Stacked / overlapping edges on one point | Distribute entry/exit points — vary `exitX`/`entryX` per edge so connections fan out across the perimeter |
| Edges crossing through shapes | Add waypoints, distribute entry/exit points, or increase spacing (200–350px) |
| Arrowhead overlaps a bend | Final segment before target must be ≥20px — increase spacing or add a waypoint |
| Clipped / truncated labels | Add `whiteSpace=wrap;html=1;`, widen the shape, or shorten the label |
| Literal `\n` in label | Use `&#xa;` for line breaks in `value` |
| Special characters in `value` | XML entities: `&amp;` `&lt;` `&gt;` `&quot;` |
| `--` inside an XML comment | Illegal per XML spec — use single hyphens or rephrase |
| Overlapping shapes | Scale spacing with complexity (200–350px); leave routing corridors |

## Export bugs

| Symptom | Fix |
|---|---|
| Vision "dimensions exceed the 2576x2576px limit" | Re-export with `--width 2000` (not `-s 2`). There is no short `-w`; passing `-w 2000` breaks input-file parsing. For tall-narrow diagrams use `--height 2000` |
| Vision 400 "Could not process image" on draft PNG | Re-export the preview without `-e` (truncated IEND in `-e` PNGs) |
| Final `-e` PNG won't open | Run `repair_png.py` (see above) |
| Background colour wrong in CLI export | Known CLI bug — add `--transparent` or set background via style |
| PDF export fails | Ensure Chromium is available (bundled on desktop) |
| Iteration loop never ends | After 5 rounds, suggest opening the `.drawio` in draw.io desktop for fine-tuning |

## Linux headless

| Symptom | Fix |
|---|---|
| Blank/error output headlessly | Prefix command with `xvfb-run -a` |
| `--no-sandbox` parsed as filename | Move `--no-sandbox` to the very end of the command |
| `Failed to get 'appData' path` | `export HOME=/tmp` before invoking drawio |
| segfault / EGL / MESA driver errors | Add `--disable-gpu` |
