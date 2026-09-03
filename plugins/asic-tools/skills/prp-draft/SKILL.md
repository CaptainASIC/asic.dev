---
name: prp-draft
description: Draft a Product Requirements Prompt (PRP) — an implementation-ready instruction document for an AI coding agent (Claude Code) to build a feature. Use when the user says "draft a PRP", "create a PRP", "turn this into a PRP", "make this a PRP", or invokes /prp-draft — typically mid-conversation after discussing a feature, or with a pasted design summary. Researches the target repo before writing; refuses with a missing-context list rather than drafting thin.
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
- `references/sizing.md` — the shared work-sizing rubric: two primary axes, boundaries, counting rules, tier → knob table

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
   Also glob `PRPs/ideas/*.md` for the `idea-refine` one-pager covering this feature and read its
   **Predicted tier** line. Selection, in order: the one-pager the user named; else the one whose
   filename slug or `# <Idea Name>` heading matches the feature ask; else none — say so and fall
   through to the feature ask's own stated counts. Two plausible candidates and no user choice is
   not a guess: list them and ask.
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
- **Size the sweep first.** Read `references/sizing.md` now — this is the first phase that needs
  it — and take the S/M/L boundaries and both counting rules from that file; never restate them
  here. Phase 2 *is* the sweep, so it cannot be its own input: take the provisional counts from
  (1) the `PRPs/ideas/` one-pager's **Predicted tier** line found in Phase 1, else (2) the
  expected task and file counts stated in the feature ask. If neither gives a number, say so and
  use M — do not invent a count. Print it marked provisional, e.g.
  `SIZING: tasks=~6 files=~5 → M (provisional: one-pager prediction; re-counted at Phase 6)`.
- Large surface area: fan-out is tier-sized per `sizing.md` — no fan-out at S, three agents at M,
  one per subsystem at L, each one a `citation-scout`. **The tier sets the count; the agent type
  sets the kind** — naming that shipped agent is what puts the fan-out on its own tier, and
  without it the agents inherit the session model with nothing reporting it.
  State the required return shape at this site — `{path, symbol, line, surprise}` per integration
  point. There is no `schema:` on a main-thread delegation, so that prose plus the rejection rule
  below *is* the shape mechanism, and the scout serves two shapes — it emits the one you name. When
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

## Phase 4.5 — Architecture panel

Once Phase 4's design decisions are settled, delegate §3's architecture selection to **three**
calls to the `architecture-judge` agent — naming that shipped agent is what puts these calls on
Fable; a prose instruction to "use Fable" resolves to the session model and nothing reports it.

Each call carries a distinct **angle**, and the angle clause is the *only* thing that differs
between them: **MVP-first** (the smallest design satisfying §2.3), **risk-first** (what fails
latest and most quietly, and what design avoids it), **constraint-first** (what the codebase's
existing patterns and caps permit). Identical payload, identical return contract — so what you
compare is answers, not briefs.

**What each call must carry.** The judge is a subagent: it inherits **none** of this conversation.
A call that names the agent and states the task alone ships a context-free judge on the most
expensive recurring seat in the pipeline. Each delegation prompt therefore carries, explicitly:

1. **The feature ask** — as settled at Phase 0/3, in full, not a summary.
2. **The settled Phase 4 answers** — every design question the interview closed, with its answer.
   These are constraints on the judge, not context for it to revisit.
3. **The Phase 2 evidence records** — the `{path, symbol, line, surprise}` entries the scouts
   returned, so the judge reasons about the real codebase and not a plausible one.
4. **The repo path**, so it can read for itself; and the §1 non-goals, so it cannot propose past
   them.

**What each must return.** State the required shape in every call prompt —
`{ decisions: [{ decision, why, alternative_rejected }] }` — and enforce it on receipt, the way
Phase 2 enforces its evidence list: **a decision returned without `alternative_rejected` is
rejected and the call re-run.** That field is how you see which part of the solution space each
angle actually explored, rather than three confident answers with the discards invisible.

The judge's brief is **goal-first** by design (it lives in the agent definition, not here): it
states the goal and the constraints rather than a procedure, because that is what the model it
runs on responds to. Do not restate it as steps in the delegation prompt.

Score the three sets against the Phase 4 answers and the §1 non-goals, then **synthesise**: take
the strongest set and graft the best individual decisions from the runners-up. The synthesis is
the main thread's, not a fourth delegated call — you have the conversation and they do not. Where
two angles disagree outright, that disagreement is the finding: record it in §3 as the decision it
forced, with the rejected side named.

**Cost, because it recurs.** Three calls at the most expensive tier in the pipeline on every PRP
drafted. **Skip the panel** when Phase 4 settled every architectural question and §3 has nothing
left to decide — three Fable calls over a foregone conclusion is an expensive restatement, and the
skip matters more with a panel than it would with one call.

## Phase 5 — Draft

Read all three reference files now. Then:

**This phase runs on the session model.** The main-thread draft is not routable from a plugin —
whatever `/model` is set to is what writes the PRP. Opus is the recommendation; there is no
mechanism here to enforce it, and a routing table pretending otherwise would be worse than this
note.


- Filename: `PRPs/PRP-NNN_TITLE_IN_SNAKE_CAPS.md`. Branch named in front matter:
  `feature/prp-NNN-short-slug`.
- Build in canonical section order (template §1–§12). Outline first, then flesh out
  section-by-section — long PRPs written in one breath go thin in §6.
- Depth scales with the tier from `references/sizing.md` — resolved absolutely from the plugin
  root (`<asic-tools skills dir>/prp-draft/references/sizing.md`), never as a relative `../`
  path, which resolves against the target repo rather than the plugin. Byte ranges (a contained
  fix ~8–15 KB with §5/§6 merged; a subsystem PRP 40–70 KB) are an **advisory corroborator**
  only: they may justify a stated escalation, never a tier on their own. Never pad — every
  sentence must carry implementation weight.
- For files >~25 KB, write the file in multiple passes (Write the front half, append the
  rest with Edit) rather than one giant emission.

## Phase 6 — Self-audit

Before reporting done, audit the draft against this list — fix, don't excuse:

- [ ] Every referenced path exists (re-check with ls/glob — catches typos)
- [ ] The `SIZING:` verdict block was emitted, with counted inputs beside the tier — re-counted
      from the written PRP using `sizing.md`'s own rules, not the Phase 2 provisional estimate
- [ ] Where a `PRPs/ideas/` one-pager exists, its **Predicted tier** was compared against the
      real count and any disagreement reported
- [ ] Every line number was read this session
- [ ] Every shell command is copy-pasteable and uses the detected tooling (`uv run …`)
- [ ] Dependency PRPs named with hard/soft designation
- [ ] Strict non-goals present (§1) and anti-patterns present (§11)
- [ ] §10 contains paste-ready PLANNING/TASKS/serena snippets, including a
      "Discovered During Work" instruction
- [ ] Git constraints embedded: feature branch, ruff-clean before commit, no AI attribution
      in commits, agent never pushes
- [ ] No `SPECULATIVE` markers remain unannounced
- [ ] Every §5 task carries at least one GATE; every runnable gate has BOTH `CHECK:` and `EXPECT:`
      (a partial gate is malformed); every manual gate has neither, names what is reviewed, AND
      justifies why no command can decide it. Flag any task whose gates are all manual, and flag a
      PRP with no runnable gate at all — the "premature done-report is structurally impossible"
      guarantee holds only for runnable gates, so an all-manual task or PRP falls back to
      self-graded prose and must be a deliberate, justified choice, not a default.

Then write the file (mkdir `PRPs/` if needed — the only file this skill writes) and report:
path, size, open questions if any, and any SPECULATIVE markers with why.

Then offer the review gate: *"Adversarially review this PRP before implementing?
(`/asic-tools:prp-review PRP-NNN`)"* — offered, never auto-run, mirroring how `idea-refine`
offers `prp-draft`.
