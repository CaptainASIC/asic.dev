---
name: okf
description: Open Knowledge Format (OKF) v0.2 — the standard shape for knowledge bundles and LLM-wikis. Use when the user says "knowledge bundle", "llm-wiki", "validate this bundle", "is this OKF conformant", "generate an index", "scaffold a knowledge base", or invokes /okf. Ships the vendored spec offline (Apache-2.0, pinned), an offline conformance validator, and a §8 index generator. Adds no dependency and needs no network.
---

# okf

Open Knowledge Format (OKF) v0.2 is the standard shape for every knowledge bundle here: a directory
of markdown files with YAML frontmatter, one required field (`type`), two reserved filenames
(`index.md`, `log.md`), and a deliberately permissive consumption model.

The spec is vendored offline at `references/okf-0.2.md`, taken verbatim from
[GoogleCloudPlatform/open-knowledge-format](https://github.com/GoogleCloudPlatform/open-knowledge-format)
(Apache-2.0, pinned — see `NOTICE.md`). v0.1 bundles are read under v0.2's §13 fallbacks:
`timestamp` and a `# Citations` body list draw migration warnings, never failures.

**Read §11 there before judging a bundle conformant. Do not judge from memory.**

## Invoking the scripts

Both helper scripts run on the ambient `python3` (no project venv, no dependencies), by absolute
path:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/<name>.py" …
```

Claude Code substitutes `${CLAUDE_SKILL_DIR}` with this skill's directory for both the plugin
install and the dev-mode symlink. Never use a `${VAR:-default}` form: only the bare `${CLAUDE_*}`
token is substituted, and the shell never has `CLAUDE_PLUGIN_ROOT` set. In the commands below
`<S>` stands for `"${CLAUDE_SKILL_DIR}"`.

## Validate a bundle

```bash
python3 <S>/scripts/validate_okf.py <bundle-root>
```

| Exit | Meaning |
|---|---|
| `0` | Conformant. Recommendation warnings may print to stderr; `--quiet` suppresses them. |
| `1` | **Non-conformant.** Each violation is named by `path` (and `line` where meaningful). |
| `2` | Usage or I/O error — the path is missing or is not a directory. |
| `3` | **Indeterminate** — a frontmatter line the parser cannot place: a column-0 line that is not `key: value` (a quoted or merge key), tab indentation, or an indented line before any key. Nested maps and block sequences under a key *are* parsed. A validator limitation, *not* a verdict. A CI gate should treat this as pass-with-warning, never as non-conformant. |

**The validator never fails a bundle for anything §11 forbids consumers to reject on**: missing
optional frontmatter fields, unknown `type` values, unknown extra keys, broken cross-links, or a
missing `index.md`. Those are warnings at most. Over-strictness is a defect, not rigour.

It also never *silently accepts*. A line it cannot read is surfaced (exit `3`), never skipped — and a
missing or empty `type` behind such a line is still an exit-`1` violation. `type: ""`, `type: ''`,
`type: null`, `type: ~`, and `type: # todo` are all an **empty** `type` (§11 rule 2), not content.

## Generate an index

```bash
python3 <S>/scripts/okf_index.py <directory>          # print to stdout
python3 <S>/scripts/okf_index.py <directory> --write  # write index.md
```

Emits the §8 shape — `* [Title](url) - description` entries under headings — and no frontmatter.
`--write` preserves any frontmatter already present, so regenerating the bundle-root `index.md`
never destroys its `okf_version` declaration.

Only the bundle-root `index.md` may carry frontmatter, and only to declare `okf_version` (§12). In
any other `index.md` it is a §8 violation.

## Append a log entry

There is no script for this — a `log.md` entry is three lines of markdown. Newest first; the date
heading MUST be ISO `YYYY-MM-DD` (§9):

```markdown
## 2026-07-10
* **Update**: Added the [orders table](/tables/orders.md).
```

## Anti-patterns

- Don't add `pyyaml` or any dependency — these scripts run under bare `python3` with no venv.
- Don't make the validator stricter than §11. A false reject is a bug.
- Don't edit
  `references/okf-0.2.md`. It is vendored verbatim and `cmp`-checkable against the pinned upstream
  commit recorded in `NOTICE.md`.
