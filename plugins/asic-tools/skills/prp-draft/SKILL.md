---
name: prp-draft
description: Draft a Product Requirements Prompt (PRP) — an implementation-ready instruction document for an AI coding agent (Claude Code or Warp) to build a feature. Use when the user says "draft a PRP", "create a PRP", "turn this into a PRP", "make this a PRP", or invokes /prp-draft — typically mid-conversation after discussing a feature, or with a pasted design summary. Researches the target repo before writing; refuses with a missing-context list rather than drafting thin.
---

# prp-draft

A PRP is a self-contained instruction set an AI agent executes to implement a feature with no
other context. Quality lives in verified specifics — real file paths, real line numbers, real
library quirks. An unverified PRP is worse than none: the implementing agent trusts it.

**Prime directive: never write a claim you have not verified.** No invented line numbers, no
guessed API signatures, no assumed file paths. Every CRITICAL/GOTCHA traces to something you
read in source, a lockfile, or official docs this session.

**Verified-context rule (see `docs/agent-tooling.md`):** every claim, decision, or gotcha that
enters the PRP carries exactly one citation — a graphify graph node, a `path:line` read this
session, or a Ref doc URL with its resolved version. A conclusion you cannot trace to one of
those is not usable: mark it `SPECULATIVE — verify before relying` and surface it. Retrieval
lanes are fixed: graphify CLI (structure) → serena (symbols/memory) → Ref (external docs).

Reference files (read when you reach the phase that needs them):
- `references/prp_template.md` — canonical section skeleton with per-section guidance
- `references/style_guide.md` — voice, formatting, and the user's standing engineering rules

## Phase 0 — Inputs

The feature ask comes from one of: the conversation so far ("turn this into a PRP"), a pasted
summary, or an explicit description. Target repo = current working directory unless the user
names another. If invoked with no discernible feature ask, ask for one — do not scaffold an
empty PRP.

## Phase 1 — Context sweep

Read, in parallel, tolerating absence:

1. `README.md`, `PLANNING.md`, `TASKS.md`, `CHANGELOG.md`
2. `WARP.md`, `CLAUDE.md` (repo-level rules)
3. `.serena/memories/` — list all; read entries relevant to the feature area, and
   `.serena/memories/prp/` for prior-PRP status memos
4. `PRPs/` — determine next number (max numeric NNN + 1, zero-padded to 3; letter suffixes
   like `028a` only when the user explicitly extends an existing PRP). Read the 1–2 most
   recent PRPs to absorb project-local conventions.
5. Tooling detection: `pyproject.toml` / `package.json` / lockfiles / `docker-compose.yml` /
   CI config. Pin actual dependency versions from the lockfile — never from memory.

If `PRPs/` does not exist, you will create it at write time and start at `PRP-001`.

When `graphify-out/wiki/index.md` exists, it is the fastest broad-navigation entry for the feature
area — prefer it to raw directory browsing for orientation.

## Phase 2 — Codebase research

This is most of the work. **When `graphify-out/graph.json` exists, lead with a graphify
orientation pass** before opening any raw file: `graphify query "<feature area>"` for a scoped
subgraph, `graphify explain "<concept>"` for a focused concept, and `graphify path "<A>" "<B>"` for
relationships — to identify which files the feature touches. This matches the repo's standing rule
(graphify before grep/`Read`) and avoids sequentially loading files that do not matter.
When no graph exists, identify the touched files directly. Either way, then read the identified
files —
entry points, services, models, config, tests. For each integration point record: exact path,
relevant symbol names, line numbers you actually saw, and any surprises (type mismatches,
sync/async boundaries, size caps already exceeded, naming drift). Graphify orients toward the files;
the verified `path:line` citation still comes from reading them.

- Verify external library claims against the installed version's docs (Ref MCP if connected,
  else WebFetch/WebSearch). Record the verified version in the PRP.
- Large surface area: fan out read-only subagents (Explore) per subsystem. When
  `graphify-out/graph.json` exists, each subagent's prompt must instruct graphify-first too —
  scope the subsystem with `graphify query`/`explain` before reading — since the directive applies
  to subagents, not only the main thread. Require each to
  return a **structured evidence list** — one record per integration point, never prose:
  `{ path, symbol, line, surprise }` (`line` = a number read this session; `surprise` = the
  gotcha, or `null`). Reject any return that summarises instead of citing — a conclusion you
  cannot trace to a `path:line` is not usable. Merge the records straight into §4: path /
  symbol / line into §4.1 references, each non-null `surprise` into a §4.4 gotcha.
- Anything you could not verify gets marked `SPECULATIVE — verify before relying` in the
  draft, and is surfaced to the user. Prefer zero of these.

## Phase 3 — Refusal gate

Do not draft unless ALL of these hold:

- [ ] Goal and desired end-state behavior are concrete (not "improve X")
- [ ] You read the actual code at every claimed integration point
- [ ] Validation commands exist and you know they run in this repo (test runner, linter)
- [ ] No blocking unknown remains that the implementing agent would have to guess at

If any fail, STOP and reply with exactly what is missing, in this shape:

```
Cannot draft PRP yet. Missing:
1. <gap> — <what would resolve it>
2. ...
```

A garbage PRP costs more than a blunt refusal.

## Phase 4 — Interview

Unresolved *design decisions* (as opposed to missing context) become questions: batch them
(max 4 per round, AskUserQuestion in Claude Code), lead with your recommendation. Typical:
scope boundary (what is explicitly OUT), config-flag default state, migration vs greenfield,
naming. Recorded answers become §3 design-decision subsections. Skip this phase only when the
conversation already settled every decision.

## Phase 5 — Draft

Read both reference files now. Then:

- Filename: `PRPs/PRP-NNN_TITLE_IN_SNAKE_CAPS.md`. Branch named in front matter:
  `feature/prp-NNN-short-slug`.
- Build in canonical section order (template §1–§12). Outline first, then flesh out
  section-by-section — long PRPs written in one breath go thin in §6.
- Depth scales with scope: a contained fix can run ~8–15 KB with §5/§6 merged; a subsystem
  PRP runs 40–70 KB. Never pad — every sentence must carry implementation weight.
- For files >~25 KB, write the file in multiple passes (Write the front half, append the
  rest with Edit) rather than one giant emission.

## Phase 6 — Self-audit

Before reporting done, audit the draft against this list — fix, don't excuse:

- [ ] Every referenced path exists (re-check with ls/glob — catches typos)
- [ ] Every line number was read this session
- [ ] Every shell command is copy-pasteable and uses the detected tooling (`uv run …`)
- [ ] Dependency PRPs named with hard/soft designation
- [ ] Strict non-goals present (§1) and anti-patterns present (§11)
- [ ] §10 contains paste-ready PLANNING/TASKS/serena snippets, including a
      "Discovered During Work" instruction
- [ ] Git constraints embedded: feature branch, ruff-clean before commit, no AI attribution
      in commits, agent never pushes
- [ ] No `SPECULATIVE` markers remain unannounced

Then write the file (mkdir `PRPs/` if needed — the only file this skill writes) and report:
path, size, open questions if any, and any SPECULATIVE markers with why.

Then offer the review gate: *"Adversarially review this PRP before implementing?
(`/asic-tools:prp-review PRP-NNN`)"* — offered, never auto-run, mirroring how `idea-refine`
offers `prp-draft`.
