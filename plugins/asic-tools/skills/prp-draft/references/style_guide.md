# PRP Style Guide

Voice, formatting, and standing engineering rules every generated PRP must encode. Derived
from the author's rule set and the established PRP corpus (Airi PRP-031…039).

## Voice

| Section | Person/tense | Register |
|---|---|---|
| §1 Objective | future ("gains", "after this PRP") | benefit-focused, zero hedging |
| §2 Problem | present, neutral | concrete, measured, no aspiration |
| §3 Architecture | prescriptive present | "must" / "never" / "required" |
| §6 Instructions | imperative | "Add this method", "Change X to Y" |
| §11 Anti-patterns | imperative negative | "Don't X. [why]" |

- **Bold** for first mention of key concepts, flags, and settings. `Backticks` for every
  identifier, field, path, env var. CAPS only for CRITICAL/GOTCHA/PATTERN/action verbs.
- No first-person. No "we should consider". A PRP states; it does not muse.
- Information-dense: reuse the codebase's own names and vocabulary so the implementing
  agent's searches hit.

## Code density targets

§6 is the densest (~70% code) — copy-paste-grade for new files, exact before/after for
edits. §4 ~70% structured blocks. §2 and §11 are nearly pure prose. If §6 is mostly prose,
the research phase was too shallow; go back.

## Gotcha taxonomy (§4.4 and inline in §6)

```python
# CRITICAL: correctness/safety boundary — violating it breaks the feature or the system.
#   Must carry evidence: verified signature, measured number, version, file:line.
# GOTCHA: non-obvious behavior that wastes an implementer's hour. Include the workaround.
# PATTERN: codebase precedent to mirror, with exemplar path.
```

Never write a gotcha from memory of how a library "usually" works. Verified or absent.

## Standing engineering rules (embed in every PRP)

These are the author's global rules; the PRP restates the ones the feature touches so the
implementing agent needs no external rule context.

**Structure caps** — files ≤500 lines, functions ≤50, classes ≤100, lines ≤100 chars.
If a task pushes a file past a cap, the task list must include the split. Pre-existing
violations get noted as a GOTCHA, not silently worsened.

**Architecture** — KISS and YAGNI govern: minimum code that solves the problem, nothing
speculative, no single-use abstractions, no unrequested configurability. Apply the
**decision ladder** (global rules) — stop at the first rung that holds (need-to-exist → stdlib
→ native → installed dep → one line → minimum) and never skip the
validation/authz/error/accessibility carve-out; PRPs encode this in §3 (architecture decisions)
and §11 (anti-patterns). Vertical slice
layout with tests beside code. Agent-shaped modules split as `agent.py` / `tools.py` /
`prompts.py`. SRP per module; fail fast — validate early, raise on invalid state, no
blanket `except Exception`.

**Python stack defaults** (greenfield; detect and defer to existing projects): `uv` for
everything (`uv add`, never hand-edit pyproject deps; `uv run` for every command), `ruff`
format + check, `mypy`, `pytest`, Pydantic v2 (`@field_validator`, `model_config =
ConfigDict(...)` — never v1 `@validator`/`class Config`), FastAPI, SQLAlchemy/SQLModel on
PostgreSQL, Redis cache when SQL in play, `python-dotenv` + pydantic-settings for config,
Google-style docstrings on every public symbol, type hints everywhere, `# Reason:` comments
for non-obvious logic.

**Database naming** — entity-specific PKs (`{entity}_id`), FKs `{referenced_entity}_id`,
timestamps `{action}_at`, booleans `is_{state}`, counts `{entity}_count`, durations
`{property}_{unit}`. Models mirror DB fields exactly. RESTful routes
(`/api/v1/{entities}/{entity_id}`).

**Testing** — TDD-shaped task ordering where practical (test task precedes or accompanies
implementation task). Per feature minimum: expected-use + edge + failure case. Tests live in
`/tests` mirroring app structure (or beside code in vertical slices — match the project).
Update existing tests whose contracts changed. Coverage target 80% on critical paths.

**Git (hard constraints, restate verbatim in §9.4)** — work on `feature/prp-NNN-slug`,
never main. Ruff clean BEFORE committing; a follow-up "applied formatting" commit is a
failure. Conventional Commits (`<type>(<scope>): <subject>`, imperative, lowercase, ≤50
chars). NO AI attribution in any commit message — no Claude, no Warp, no Co-Authored-By.
The agent never pushes; the user pushes via GitKraken.

**Surgical scope** — every changed line traces to a §5 task. No adjacent improvements, no
drive-by refactors, match existing style. Remove only orphans created by this PRP's own
changes. Never delete pre-existing code unless a task says so.

**MCP usage (when the implementing environment has them)** — Serena for project memory
(§10.3 writes there); Ref to verify library APIs before coding against them. PRPs
reference these as available tools, not hard dependencies.

## Length calibration

| Scope | Typical size | Shape |
|---|---|---|
| Contained fix (≤3 files) | 8–15 KB | §3 two subsections; §5+§6 may merge |
| Feature (4–10 files) | 25–45 KB | full skeleton |
| Subsystem / infra | 45–75 KB | §3 runs 5–11 subsections; §6 per-file |

Size is an output of research depth, never a target. Padding is a defect.

## Numbering & files

- Next PRP = max numeric `NNN` in `PRPs/` + 1, zero-padded 3 (`PRP-040`).
- Letter suffix (`PRP-028a`) only for explicit follow-ons to a parent PRP.
- Filename `PRP-NNN_TITLE_IN_SNAKE_CAPS.md`. The PRP file is the only artifact drafting
  writes — TASKS/PLANNING/serena updates happen post-implementation via §10.
