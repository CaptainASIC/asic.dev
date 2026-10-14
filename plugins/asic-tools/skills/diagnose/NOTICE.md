# Attribution

The `diagnose` skill is adapted from two MIT-licensed debugging skills. The text was rewritten to
this toolbox's conventions: uv and pytest examples, graphify-first orientation, the global rules'
regression-test-first and no-throwaway-scripts rules, and a hand-off to `prp-draft`. No upstream
file is vendored verbatim and no upstream script is shipped.

| Upstream | Files read | Pinned commit | Used for |
|---|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | `skills/systematic-debugging/` — `SKILL.md`, `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md` | `bb92a77741419a4ab5f06e711a283343f1ada0c3` (2026-10-10) | the iron law, investigation steps, three-strikes rule, red flags, root-cause tracing, hardening |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `skills/engineering/diagnosing-bugs/SKILL.md` | `49dd158d1076134a641b33efb035946536778336` (2026-10-09) | loop-first phase order, loop constructions, the Phase 1 completion criterion, ranked falsifiable hypotheses, tagged debug logs, redaction |

Deliberately not carried over:

- `find-polluter.sh` (superpowers) runs `npm test` per file. `references/root-cause-tracing.md`
  describes the same technique as a pytest loop.
- `scripts/hitl-loop.template.sh` (mattpocock) prompts with interactive `read`, which the Bash
  tool cannot answer. Replaced by having the user perform the step, then run a non-interactive
  capture command with `! <command>`.
- References to other upstream skills (`superpowers:*`) and the `GLOSSARY.md` / ADR conventions,
  which this toolbox does not have.

## Staleness

Both upstreams change often. Before editing this skill, compare the pinned commits with upstream:

    git ls-remote https://github.com/obra/superpowers refs/heads/main
    git ls-remote https://github.com/mattpocock/skills refs/heads/main

A different commit means: re-read the upstream files listed above, then update this notice.

## obra/superpowers — MIT License

```
MIT License

Copyright (c) 2025 Jesse Vincent

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

## mattpocock/skills — MIT License

```
MIT License

Copyright (c) 2026 Matt Pocock

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
