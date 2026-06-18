# Attribution

The `diagram` skill is ported and adapted from
[Agents365-ai/drawio-skill](https://github.com/Agents365-ai/drawio-skill) (MIT License), pinned at
tag **`v1.14.0`**. The scripts and reference docs were rewritten to Captain ASIC's engineering
conventions (ruff @ line-length 100, type hints on every signature, Google-style docstrings,
≤500-line files, stdlib `logging` for diagnostics); the behaviour and CLI contracts of each script
are preserved.

## Upstream skill — MIT

```
MIT License

Copyright (c) 2026 Agents365-ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Vendored data — separate licenses

- **`data/shape-index.json.gz`** — the 10k+ shape search index, **Apache License 2.0**, sourced
  from [jgraph/drawio-mcp](https://github.com/jgraph/drawio-mcp) (generated from the official
  draw.io / diagrams.net client shape libraries). See `data/SHAPE-INDEX-NOTICE.md` for provenance
  and refresh instructions.
- **`data/lobe-icons.json`** — AI/LLM brand-logo index derived from
  [lobehub/lobe-icons](https://github.com/lobehub/lobe-icons); logos are served via CDN
  (`unpkg.com/@lobehub/icons-static-svg`) and remain the property of their respective brand owners.
- **`styles/built-in/*.json`** — the three built-in style presets, carried over from the upstream
  skill (MIT, as above).
